from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportExplicitAny=false, reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnannotatedClassAttribute=false, reportImplicitOverride=false

import re
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import cast

from stock_hub.scrapers.base import BaseScraper
from stock_hub.scrapers.http_client import HttpClient
from stock_hub.storage.models import Post


class CNInfoScraper(BaseScraper):
    source_name: str = "cninfo"

    _api_url: str = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    _static_url: str = "http://static.cninfo.com.cn/"
    _headers: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "http://www.cninfo.com.cn/",
    }
    _stock_code_pattern: re.Pattern[str] = re.compile(r"\b(\d{6})\b")

    def __init__(self, client: HttpClient | None = None) -> None:
        self.client: HttpClient = client or HttpClient()

    async def fetch_latest(self, limit: int = 30) -> list[object]:
        payload = self._build_payload(limit=limit)
        return cast(list[object], await self._request_posts(payload))

    async def search(self, keyword: str, limit: int = 30) -> list[object]:
        payload = self._build_payload(limit=limit, searchkey=keyword)
        return cast(list[object], await self._request_posts(payload))

    def parse_announcements(self, payload: dict[str, object]) -> list[Post]:
        raw_announcements = payload.get("announcements", [])
        announcements: Iterable[object] = []
        if isinstance(raw_announcements, list):
            announcements = cast(list[object], raw_announcements)
        posts: list[Post] = []

        for announcement in announcements:
            if not isinstance(announcement, dict):
                continue

            title = str(announcement.get("announcementTitle", "")).strip()
            content = str(announcement.get("announcementContent", "")).strip()
            adjunct_url = str(announcement.get("adjunctUrl", "")).lstrip("/")
            posts.append(
                Post(
                    source=self.source_name,
                    title=title,
                    content=content,
                    author="",
                    url=self._build_url(adjunct_url),
                    stock_codes=self.extract_stock_codes(title),
                    published_at=self._normalize_cninfo_time(announcement.get("announcementTime", "")),
                    scraped_at="",
                )
            )

        return posts

    def extract_stock_codes(self, title: str) -> list[str]:
        return list(dict.fromkeys(self._stock_code_pattern.findall(title)))

    def _normalize_cninfo_time(self, raw: object) -> str:
        """CNInfo returns either a 13-digit millisecond timestamp or ISO string."""
        if not raw:
            return ""
        text = str(raw).strip()
        # 13-digit millisecond timestamp
        if text.isdigit() and len(text) == 13:
            try:
                return datetime.fromtimestamp(int(text) / 1000, tz=timezone.utc).isoformat()
            except (ValueError, OSError):
                return text
        return text

    def _build_payload(self, limit: int, **extra: str) -> dict[str, str | int]:
        payload: dict[str, str | int] = {
            "tabName": "fulltext",
            "pageSize": limit,
            "pageNum": 1,
            "isHLtitle": "true",
        }
        payload.update(extra)
        return payload

    async def _request_posts(self, payload: dict[str, str | int]) -> list[Post]:
        response = await self.client.post(self._api_url, data=payload, headers=self._headers)
        _ = response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return []
        return self.parse_announcements(cast(dict[str, object], data))

    def _build_url(self, adjunct_url: str) -> str:
        if not adjunct_url:
            return ""
        return f"{self._static_url}{adjunct_url}"
