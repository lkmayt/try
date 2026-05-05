from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import cast, override

from stock_hub.config import get_config
from stock_hub.scrapers.base import BaseScraper
from stock_hub.scrapers.http_client import HttpClient
from stock_hub.storage.models import Post


class JiuyangongsheScraper(BaseScraper):
    source_name: str = "jiuyan"

    COMMUNITY_URL: str = "https://app.jiuyangongshe.com/jystock-app/api/v2/article/community"
    SEARCH_URL: str = "https://app.jiuyangongshe.com/jystock-app/api/v2/article/search"

    def __init__(self, client: HttpClient | None = None) -> None:
        self.client: HttpClient = client or HttpClient()

    def _generate_auth_headers(self) -> dict[str, str]:
        config = cast(dict[str, object], get_config())
        scrapers = cast(dict[str, object], config.get("scrapers", {}))
        jiuyan = cast(dict[str, object], scrapers.get("jiuyan", {}))
        salt = str(jiuyan.get("salt", "Uu0KfOB8iUP69d3c"))
        timestamp = str(int(time.time() * 1000))
        token = hashlib.md5(f"{salt}:{timestamp}".encode()).hexdigest()
        return {
            "platform": "3",
            "timestamp": timestamp,
            "token": token,
        }

    @override
    async def fetch_latest(self, limit: int = 30) -> list[object]:
        payload = {
            "category_id": "",
            "limit": limit,
            "order": 0,
            "start": 1,
            "type": 0,
            "back_garden": 0,
        }
        response = await self.client.post(
            self.COMMUNITY_URL,
            json=payload,
            headers={
                **self._generate_auth_headers(),
                "Referer": "https://www.jiuyangongshe.com/",
            },
        )
        _ = response.raise_for_status()
        return cast(list[object], self._parse_posts(cast(dict[str, object], response.json())))

    @override
    async def search(self, keyword: str, limit: int = 30) -> list[object]:
        payload = {"keyword": keyword, "limit": limit, "start": 1}
        response = await self.client.post(
            self.SEARCH_URL,
            json=payload,
            headers=self._generate_auth_headers(),
        )
        _ = response.raise_for_status()
        return cast(list[object], self._parse_posts(cast(dict[str, object], response.json())))

    def _parse_posts(self, payload: dict[str, object]) -> list[Post]:
        data = payload.get("data", {})
        if not isinstance(data, dict):
            return []
        # API returns data.result, not data.list
        records = data.get("result", data.get("list", []))
        if not isinstance(records, list):
            return []
        return [self._record_to_post(cast(dict[str, object], record)) for record in records if isinstance(record, dict)]

    def _record_to_post(self, record: dict[str, object]) -> Post:
        article_id = record.get("article_id", record.get("id", ""))
        return Post(
            source=self.source_name,
            title=str(record.get("title", "")),
            content=str(record.get("content", "")),
            author=str(record.get("user_id", record.get("user_name", ""))),
            url=self._build_article_url(article_id),
            stock_codes=self._extract_stock_codes(record.get("stock_list", [])),
            published_at=str(record.get("create_time", record.get("created_at", ""))),
            scraped_at=datetime.now(timezone.utc).isoformat(),
            id=int(article_id) if isinstance(article_id, int) or (isinstance(article_id, str) and article_id.isdigit()) else None,
        )

    def _build_article_url(self, article_id: object) -> str:
        if article_id in (None, ""):
            return ""
        return f"https://www.jiuyangongshe.com/a/{article_id}"

    def _extract_stock_codes(self, stock_list: object) -> list[str]:
        if not isinstance(stock_list, list):
            return []
        codes: list[str] = []
        for item in stock_list:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code", "")).strip()
            if code:
                codes.append(code)
        return codes
