from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

from stock_hub.scrapers.base import BaseScraper
from stock_hub.scrapers.http_client import HttpClient
from stock_hub.storage.models import Post


class SSEInteractiveScraper(BaseScraper):
    source_name = "sse"

    def __init__(self, http_client: HttpClient | None = None, use_akshare: bool = True) -> None:
        self.client = http_client or HttpClient()
        self._use_akshare = use_akshare

    async def fetch_latest(self, limit: int = 30) -> list[Post]:
        if self._use_akshare:
            posts = await self._fetch_via_akshare(limit=limit)
            if posts:
                return posts[:limit]
        return await self._fetch_via_http(limit=limit)

    async def search(self, keyword: str, limit: int = 30) -> list[Post]:
        if self._use_akshare:
            posts = await self._fetch_via_akshare(limit=limit, keyword=keyword)
            if posts:
                return posts[:limit]
        return await self._fetch_via_http(limit=limit, keyword=keyword)

    async def _fetch_via_akshare(self, limit: int, keyword: str | None = None) -> list[Post]:
        try:
            import akshare as ak  # type: ignore
        except Exception:
            return []

        # Only use akshare if searching for a specific stock; "all" is too slow
        if not keyword or keyword == "all":
            return []
        
        try:
            import asyncio
            df = await asyncio.to_thread(ak.stock_sns_sseinfo, symbol=keyword)
        except Exception:
            return []
        
        if df is None or getattr(df, "empty", True):
            return []
        return [self._row_to_post(row) for _, row in df.head(limit).iterrows()]

    async def _fetch_via_http(self, limit: int, keyword: str | None = None) -> list[Post]:
        # AKShare uses POST with Referer header for SSE API
        headers = {
            "Referer": "https://sns.sseinfo.com/",
        }
        data = {
            "type": "11",
            "pageSize": str(limit),
            "page": "1",
            "lastid": "-1",
            "show": "1",
        }
        if keyword and keyword != "all":
            data["keyword"] = keyword

        response = await self.client.post(
            "http://sns.sseinfo.com/ajax/feeds.do",
            data=data,
            headers=headers,
        )
        if response.status_code >= 400:
            return []
        return self._parse_html(response.text, limit=limit)

    # _build_url removed — POST-based API used instead

    def _parse_html(self, html: str, limit: int) -> list[Post]:
        soup = BeautifulSoup(html, "html.parser")
        posts: list[Post] = []
        for item in soup.select("div.m_feed_item")[:limit]:
            author = self._text_or_empty(item.select_one(".m_feed_face a"))
            texts = [self._text_or_empty(node) for node in item.select(".m_feed_txt")]
            title = texts[0] if texts else ""
            answer = texts[1] if len(texts) > 1 else ""
            published_at = self._text_or_empty(item.select_one(".m_feed_from"))
            url = f"http://sns.sseinfo.com/{item.get('id', '')}" if item.get("id") else "http://sns.sseinfo.com/"
            posts.append(
                Post(
                    source=self.source_name,
                    title=title,
                    content="\n".join([part for part in [title, answer] if part]),
                    author=author,
                    url=url,
                    published_at=published_at,
                    scraped_at=self._now_iso(),
                )
            )
        return posts

    def _row_to_post(self, row: Any) -> Post:
        title = str(row.get("question", row.get("title", "")))
        answer = str(row.get("answer", row.get("content", "")))
        return Post(
            source=self.source_name,
            title=title,
            content="\n".join([part for part in [title, answer] if part]),
            author=str(row.get("author", row.get("questioner", ""))),
            url=str(row.get("url", "")),
            stock_codes=self._to_stock_codes(row.get("stock_codes", row.get("symbol", ""))),
            published_at=str(row.get("published_at", "")),
            scraped_at=self._now_iso(),
        )

    def _to_stock_codes(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v) for v in value if str(v)]
        text = str(value).strip()
        return [text] if text else []

    def _text_or_empty(self, node: Any) -> str:
        return node.get_text(strip=True) if node else ""

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
