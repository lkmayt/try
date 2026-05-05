from __future__ import annotations

from datetime import datetime, timedelta
import json
import re
import sqlite3

from stock_hub.storage.models import Post

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")


def _iso_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _cjk_bigrams(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _CJK_RE.finditer(text):
        segment = match.group(0)
        if len(segment) < 2:
            continue
        tokens.extend(segment[index : index + 2] for index in range(len(segment) - 1))
    return tokens


def _augment_for_fts(text: str) -> str:
    normalized = text.strip()
    if not normalized:
        return ""
    bigrams = _cjk_bigrams(normalized)
    if not bigrams:
        return normalized
    return " ".join([normalized, *bigrams])


def _prepare_match_query(query: str) -> str:
    normalized = query.strip()
    if not normalized:
        return ""

    bigrams = _cjk_bigrams(normalized)
    if bigrams:
        unique_bigrams = list(dict.fromkeys(bigrams))
        exact_term = json.dumps(normalized, ensure_ascii=False)
        bigram_terms = " AND ".join(json.dumps(token, ensure_ascii=False) for token in unique_bigrams)
        return f"{exact_term} OR ({bigram_terms})"

    return normalized


class Database:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.create_function("fts_index_text", 1, _augment_for_fts)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.init_db()

    def init_db(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS posts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source TEXT NOT NULL,
              title TEXT NOT NULL,
              content TEXT DEFAULT '',
              author TEXT DEFAULT '',
              url TEXT DEFAULT '',
              stock_codes TEXT DEFAULT '[]',
              published_at TEXT DEFAULT '',
              scraped_at TEXT NOT NULL,
              UNIQUE(source, url)
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
              title, content, author, stock_codes,
              content='posts',
              content_rowid='id',
              tokenize='unicode61'
            );

            CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN
              INSERT INTO posts_fts(rowid, title, content, author, stock_codes)
              VALUES (
                new.id,
                fts_index_text(new.title),
                fts_index_text(new.content),
                fts_index_text(new.author),
                fts_index_text(new.stock_codes)
              );
            END;

            CREATE TRIGGER IF NOT EXISTS posts_ad AFTER DELETE ON posts BEGIN
              INSERT INTO posts_fts(posts_fts, rowid, title, content, author, stock_codes)
              VALUES(
                'delete',
                old.id,
                fts_index_text(old.title),
                fts_index_text(old.content),
                fts_index_text(old.author),
                fts_index_text(old.stock_codes)
              );
            END;

            CREATE TRIGGER IF NOT EXISTS posts_au AFTER UPDATE ON posts BEGIN
              INSERT INTO posts_fts(posts_fts, rowid, title, content, author, stock_codes)
              VALUES(
                'delete',
                old.id,
                fts_index_text(old.title),
                fts_index_text(old.content),
                fts_index_text(old.author),
                fts_index_text(old.stock_codes)
              );
              INSERT INTO posts_fts(rowid, title, content, author, stock_codes)
              VALUES (
                new.id,
                fts_index_text(new.title),
                fts_index_text(new.content),
                fts_index_text(new.author),
                fts_index_text(new.stock_codes)
              );
            END;

            CREATE TABLE IF NOT EXISTS keywords (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              keyword TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL
            );
            """
        )

        self.connection.execute("INSERT INTO posts_fts(posts_fts) VALUES('rebuild')")
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def _serialize_stock_codes(self, stock_codes: list[str]) -> str:
        return json.dumps(stock_codes, ensure_ascii=False)

    def _deserialize_post(self, row: sqlite3.Row) -> Post:
        return Post(
            id=row["id"],
            source=row["source"],
            title=row["title"],
            content=row["content"],
            author=row["author"],
            url=row["url"],
            stock_codes=json.loads(row["stock_codes"] or "[]"),
            published_at=row["published_at"],
            scraped_at=row["scraped_at"],
        )

    def _post_values(self, post: Post) -> tuple[str, str, str, str, str, str, str, str]:
        scraped_at = post.scraped_at or _iso_now()
        return (
            post.source,
            post.title,
            post.content,
            post.author,
            post.url,
            self._serialize_stock_codes(post.stock_codes),
            post.published_at,
            scraped_at,
        )

    def insert_post(self, post: Post) -> int | None:
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO posts (
                source, title, content, author, url, stock_codes, published_at, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._post_values(post),
        )
        self.connection.commit()

        if cursor.rowcount == 0:
            return None

        post_id = int(cursor.lastrowid)
        post.id = post_id
        if not post.scraped_at:
            row = self.connection.execute(
                "SELECT scraped_at FROM posts WHERE id = ?",
                (post_id,),
            ).fetchone()
            if row is not None:
                post.scraped_at = row["scraped_at"]
        return post_id

    def get_post_by_id(self, post_id: int) -> Post | None:
        row = self.connection.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if row is None:
            return None
        return self._deserialize_post(row)

    def update_post(self, post: Post) -> bool:
        if post.id is None:
            raise ValueError("post.id is required for update")

        cursor = self.connection.execute(
            """
            UPDATE posts
            SET source = ?, title = ?, content = ?, author = ?, url = ?, stock_codes = ?,
                published_at = ?, scraped_at = ?
            WHERE id = ?
            """,
            (*self._post_values(post), post.id),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def delete_post(self, post_id: int) -> None:
        self.connection.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        self.connection.commit()

    def count_search_posts(self, query: str, source: str | None = None) -> int:
        match_query = _prepare_match_query(query)
        if not match_query:
            return 0

        sql = (
            "SELECT COUNT(*) AS total FROM posts_fts "
            "JOIN posts ON posts.id = posts_fts.rowid "
            "WHERE posts_fts MATCH ?"
        )
        params: list[object] = [match_query]
        if source is not None:
            sql += " AND posts.source = ?"
            params.append(source)

        row = self.connection.execute(sql, params).fetchone()
        return int(row["total"]) if row is not None else 0

    def search_posts(
        self,
        query: str,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Post]:
        match_query = _prepare_match_query(query)
        if not match_query:
            return []

        sql = (
            "SELECT posts.* FROM posts_fts "
            "JOIN posts ON posts.id = posts_fts.rowid "
            "WHERE posts_fts MATCH ?"
        )
        params: list[object] = [match_query]
        if source is not None:
            sql += " AND posts.source = ?"
            params.append(source)
        sql += " ORDER BY bm25(posts_fts), posts.scraped_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.connection.execute(sql, params).fetchall()
        results = [self._deserialize_post(row) for row in rows]

        # LIKE fallback for partial Chinese queries that FTS5 might miss
        if not results and len(query) >= 2:
            sql = (
                "SELECT posts.* FROM posts "
                "WHERE (posts.title LIKE ? OR posts.content LIKE ?)"
            )
            params = [f"%{query}%", f"%{query}%"]
            if source is not None:
                sql += " AND posts.source = ?"
                params.append(source)
            sql += " ORDER BY posts.scraped_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            like_rows = self.connection.execute(sql, params).fetchall()
            results = [self._deserialize_post(row) for row in like_rows]

        return results

    def search_by_like(
        self,
        keywords: list[str],
        source: str | None = None,
        limit: int = 50,
    ) -> list[Post]:
        """Broad LIKE search across title+content for any of the given keywords."""
        clauses = ["posts.title LIKE ?", "posts.content LIKE ?"]
        params: list[object] = []
        for kw in keywords:
            params.extend([f"%{kw}%", f"%{kw}%"])
        sql = "SELECT posts.* FROM posts WHERE (" + " OR ".join(clauses) + ")"
        if source is not None:
            sql += " AND posts.source = ?"
            params.append(source)
        sql += " ORDER BY posts.scraped_at DESC LIMIT ?"
        params.append(limit)
        rows = self.connection.execute(sql, params).fetchall()
        return [self._deserialize_post(row) for row in rows]

    def search_posts_with_count(
        self,
        query: str,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Post], int]:
        return self.search_posts(query=query, source=source, limit=limit, offset=offset), self.count_search_posts(
            query=query,
            source=source,
        )

    def get_posts_by_stock(
        self,
        stock_code: str,
        source: str | None = None,
        limit: int = 50,
    ) -> list[Post]:
        sql = (
            "SELECT posts.* FROM posts "
            "WHERE EXISTS (SELECT 1 FROM json_each(posts.stock_codes) WHERE json_each.value = ?)"
        )
        params: list[object] = [stock_code]
        if source is not None:
            sql += " AND posts.source = ?"
            params.append(source)
        sql += " ORDER BY posts.scraped_at DESC LIMIT ?"
        params.append(limit)

        rows = self.connection.execute(sql, params).fetchall()
        return [self._deserialize_post(row) for row in rows]

    def get_recent_posts(self, source: str | None = None, limit: int = 50) -> list[Post]:
        sql = "SELECT * FROM posts"
        params: list[object] = []
        if source is not None:
            sql += " WHERE source = ?"
            params.append(source)
        sql += " ORDER BY scraped_at DESC LIMIT ?"
        params.append(limit)

        rows = self.connection.execute(sql, params).fetchall()
        return [self._deserialize_post(row) for row in rows]

    def cleanup_old_posts(self, days: int = 90) -> None:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat(timespec="seconds")
        self.connection.execute("DELETE FROM posts WHERE scraped_at < ?", (cutoff,))
        self.connection.commit()

    def get_source_stats(self) -> dict[str, dict[str, str | int | None]]:
        rows = self.connection.execute(
            """
            SELECT source, COUNT(*) AS count, MAX(scraped_at) AS latest_scraped_at
            FROM posts
            GROUP BY source
            ORDER BY source
            """
        ).fetchall()
        return {
            row["source"]: {"count": int(row["count"]), "latest_scraped_at": row["latest_scraped_at"]}
            for row in rows
        }

    def add_keyword(self, keyword: str) -> int:
        created_at = _iso_now()
        cursor = self.connection.execute(
            "INSERT INTO keywords (keyword, created_at) VALUES (?, ?)",
            (keyword, created_at),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def delete_keyword(self, keyword_id: int) -> None:
        self.connection.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
        self.connection.commit()

    def get_keywords(self) -> list[dict[str, str | int]]:
        rows = self.connection.execute(
            "SELECT id, keyword, created_at FROM keywords ORDER BY id"
        ).fetchall()
        return [
            {"id": int(row["id"]), "keyword": row["keyword"], "created_at": row["created_at"]}
            for row in rows
        ]
