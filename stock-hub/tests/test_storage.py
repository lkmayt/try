from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from datetime import UTC, datetime, timedelta

from stock_hub.storage.database import Database
from stock_hub.storage.models import Post


def make_post(
    *,
    source: str = "cninfo",
    title: str = "默认标题",
    content: str = "默认内容",
    author: str = "测试作者",
    url: str = "https://example.com/default",
    stock_codes: list[str] | None = None,
    published_at: str = "2026-01-01T09:30:00",
    scraped_at: str = "2026-01-01T09:35:00",
) -> Post:
    return Post(
        source=source,
        title=title,
        content=content,
        author=author,
        url=url,
        stock_codes=list(stock_codes or ["600519"]),
        published_at=published_at,
        scraped_at=scraped_at,
    )


def test_insert_and_retrieve_post(database: Database) -> None:
    post = make_post(title="插入测试", url="https://example.com/insert")

    post_id = database.insert_post(post)
    stored = database.get_post_by_id(post_id or -1)

    assert post_id is not None
    assert stored is not None
    assert stored.title == "插入测试"
    assert stored.stock_codes == ["600519"]
    assert stored.source == "cninfo"


def test_dedup_by_source_url(database: Database) -> None:
    first = make_post(title="公告", url="https://example.com/dedup")
    second = make_post(title="公告重复", url="https://example.com/dedup")

    first_id = database.insert_post(first)
    second_id = database.insert_post(second)

    assert first_id is not None
    assert second_id is None
    assert len(database.get_recent_posts()) == 1


def test_chinese_fts_search(database: Database) -> None:
    _ = database.insert_post(
        make_post(
            title="贵州茅台白酒景气度提升",
            content="机构持续关注茅台与高端白酒需求。",
            url="https://example.com/maotai",
        )
    )

    results, total = database.search_posts_with_count("茅台")

    assert total == 1
    assert len(results) == 1
    assert results[0].title == "贵州茅台白酒景气度提升"


def test_fts_search_no_results(database: Database) -> None:
    _ = database.insert_post(make_post(title="市场复盘", url="https://example.com/market"))

    results, total = database.search_posts_with_count("完全不存在的关键词")

    assert total == 0
    assert results == []


def test_source_filtering(database: Database) -> None:
    _ = database.insert_post(make_post(source="cninfo", title="回购公告", url="https://example.com/source-1"))
    _ = database.insert_post(make_post(source="sse", title="回购公告", url="https://example.com/source-2"))
    _ = database.insert_post(make_post(source="szse", title="回购公告", url="https://example.com/source-3"))

    results = database.search_posts("回购", source="sse")

    assert len(results) == 1
    assert results[0].source == "sse"


def test_get_recent_posts_ordering(database: Database) -> None:
    _ = database.insert_post(make_post(title="最早", url="https://example.com/recent-1", scraped_at="2026-01-01T08:00:00"))
    _ = database.insert_post(make_post(title="中间", url="https://example.com/recent-2", scraped_at="2026-01-01T09:00:00"))
    _ = database.insert_post(make_post(title="最新", url="https://example.com/recent-3", scraped_at="2026-01-01T10:00:00"))

    posts = database.get_recent_posts(limit=3)

    assert [post.title for post in posts] == ["最新", "中间", "最早"]


def test_cleanup_old_posts(database: Database) -> None:
    old_scraped_at = (datetime.now(UTC) - timedelta(days=120)).replace(tzinfo=None).isoformat(timespec="seconds")
    recent_scraped_at = datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")
    _ = database.insert_post(make_post(title="旧帖子", url="https://example.com/old", scraped_at=old_scraped_at))
    _ = database.insert_post(make_post(title="新帖子", url="https://example.com/new", scraped_at=recent_scraped_at))

    database.cleanup_old_posts(days=90)
    titles = [post.title for post in database.get_recent_posts(limit=10)]

    assert titles == ["新帖子"]


def test_keyword_crud(database: Database) -> None:
    keyword_id = database.add_keyword("人工智能")

    keywords = database.get_keywords()
    assert len(keywords) == 1
    assert keywords[0]["id"] == keyword_id
    assert keywords[0]["keyword"] == "人工智能"
    assert keywords[0]["created_at"]

    database.delete_keyword(keyword_id)

    assert database.get_keywords() == []


def test_get_posts_by_stock(database: Database) -> None:
    _ = database.insert_post(
        make_post(
            title="茅台公告",
            url="https://example.com/stock-1",
            stock_codes=["600519", "000001"],
        )
    )
    _ = database.insert_post(
        make_post(
            title="宁德时代调研",
            url="https://example.com/stock-2",
            stock_codes=["300750"],
        )
    )

    posts = database.get_posts_by_stock("600519")

    assert len(posts) == 1
    assert posts[0].title == "茅台公告"


def test_get_source_stats(database: Database) -> None:
    _ = database.insert_post(make_post(source="cninfo", title="公告A", url="https://example.com/stats-1", scraped_at="2026-01-01T09:00:00"))
    _ = database.insert_post(make_post(source="cninfo", title="公告B", url="https://example.com/stats-2", scraped_at="2026-01-01T10:00:00"))
    _ = database.insert_post(make_post(source="sse", title="公告C", url="https://example.com/stats-3", scraped_at="2026-01-01T08:00:00"))

    stats = database.get_source_stats()

    assert stats["cninfo"]["count"] == 2
    assert stats["cninfo"]["latest_scraped_at"] == "2026-01-01T10:00:00"
    assert stats["sse"]["count"] == 1
