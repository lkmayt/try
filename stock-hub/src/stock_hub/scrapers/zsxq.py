from __future__ import annotations

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportAny=false

import hashlib
import logging
import re
import time
from typing import override
from urllib.parse import urlencode

from stock_hub.config import get_config
from stock_hub.scrapers.base import BaseScraper
from stock_hub.scrapers.http_client import HttpClient
from stock_hub.storage.models import Post


logger = logging.getLogger(__name__)

SECRET = "zsxqapi2020"
_COMMON_PARAMS = {"app_version": "3.11.0", "platform": "ios"}


class ZsxqScraper(BaseScraper):
    source_name: str = "zsxq"

    def __init__(self, http_client: HttpClient | None = None, config: dict[object, object] | None = None) -> None:
        self.http_client: HttpClient = http_client or HttpClient()
        self.config: dict[object, object] = config if config is not None else get_config()

    @override
    async def fetch_latest(self, limit: int = 20) -> list[object]:
        scraper_config = self._get_scraper_config()
        cookie = str(scraper_config.get("cookie", "")).strip()
        if not cookie:
            logger.info("Zsxq: no cookie configured, skipping")
            return []

        group_ids = scraper_config.get("group_ids", [])
        if not isinstance(group_ids, list) or len(group_ids) == 0:
            # Auto-discover joined groups
            logger.info("Zsxq: no group_ids configured, auto-discovering...")
            groups = await self._fetch_joined_groups(cookie)
            if not groups:
                logger.warning("Zsxq: could not discover any groups")
                return []
            group_ids = groups

        posts: list[Post] = []
        for group_id in group_ids:
            group_id_str = str(group_id).strip()
            if not group_id_str:
                continue

            path = f"/v2/groups/{group_id_str}/topics"
            params = {"count": str(limit), "scope": "all"}
            signature, timestamp = self._generate_signature(path, params=params)
            url = f"https://api.zsxq.com{path}?{urlencode(params)}"
            logger.info("Zsxq: fetching group %s", group_id_str)
            response = await self.http_client.get(
                url,
                headers={
                    "Origin": "https://wx.zsxq.com",
                    "Referer": "https://wx.zsxq.com/",
                    "Cookie": cookie,
                    "X-Signature": signature,
                    "X-Timestamp": timestamp,
                },
            )

            if response.status_code == 401:
                logger.warning("Zsxq: Cookie 已过期 (401)")
                return []

            payload = response.json()
            if not isinstance(payload, dict):
                logger.warning("Zsxq: unexpected response format")
                return []
            if not payload.get("succeeded", False):
                error_msg = payload.get("error", payload.get("msg", "unknown"))
                logger.warning("Zsxq: API returned succeeded=false, error=%s", error_msg)
                return []

            parsed = self._parse_topics(payload, group_id=group_id_str)
            logger.info("Zsxq: group %s returned %d topics", group_id_str, len(parsed))
            posts.extend(parsed)
        return list(posts[:limit])

    @override
    async def search(self, keyword: str, limit: int = 20) -> list[object]:
        return []

    def _get_scraper_config(self) -> dict[object, object]:
        scrapers = self.config.get("scrapers", {})
        if not isinstance(scrapers, dict):
            return {}
        scraper_config = scrapers.get(self.source_name, {})
        return scraper_config if isinstance(scraper_config, dict) else {}

    async def _fetch_joined_groups(self, cookie: str) -> list[str]:
        """Auto-discover groups the user has joined."""
        path = "/v2/groups"
        params = {"count": "50"}
        signature, timestamp = self._generate_signature(path, params=params)
        url = f"https://api.zsxq.com{path}?{urlencode(params)}"
        response = await self.http_client.get(
            url,
            headers={
                "Origin": "https://wx.zsxq.com",
                "Referer": "https://wx.zsxq.com/",
                "Cookie": cookie,
                "X-Signature": signature,
                "X-Timestamp": timestamp,
            },
        )
        if response.status_code != 200:
            return []
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("succeeded"):
            return []
        groups = payload.get("resp_data", {}).get("groups", [])
        ids = [str(g.get("group_id", "")) for g in groups if isinstance(g, dict)]
        logger.info("Zsxq: auto-discovered %d groups: %s", len(ids), ids)
        return ids

    def _generate_signature(
        self,
        path: str,
        params: dict[str, str] | None = None,
        timestamp: str | None = None,
    ) -> tuple[str, str]:
        ts = timestamp or str(int(time.time() * 1000))
        common = {**_COMMON_PARAMS, "timestamp": ts}
        all_params = {**common, **(params or {})}
        sorted_params = sorted(all_params.items(), key=lambda item: item[0])
        params_str = urlencode(sorted_params)
        sign_str = f"{path}&{params_str}&{SECRET}"
        signature = hashlib.md5(sign_str.encode()).hexdigest()
        return signature, ts

    def _parse_topics(self, payload: dict[object, object], group_id: str) -> list[Post]:
        resp_data = payload.get("resp_data", {})
        if not isinstance(resp_data, dict):
            return []
        topics = resp_data.get("topics", [])
        if not isinstance(topics, list):
            return []

        posts: list[Post] = []
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            text = self._extract_topic_text(topic)
            if not text:
                continue
            author = self._extract_author(topic)
            topic_id = topic.get("topic_id", "")
            posts.append(
                Post(
                    source=self.source_name,
                    title=text[:80],
                    content=text,
                    author=author,
                    url=f"https://wx.zsxq.com/group/{group_id}/topic/{topic_id}",
                    stock_codes=self._extract_stock_codes(text),
                    published_at=str(topic.get("create_time", "")),
                )
            )
        return posts

    def _extract_topic_text(self, topic: dict[object, object]) -> str:
        talk = topic.get("talk", {})
        if isinstance(talk, dict):
            text = str(talk.get("text", "")).strip()
            if text:
                return text

        question = topic.get("question", {})
        if isinstance(question, dict):
            return str(question.get("text", "")).strip()
        return ""

    def _extract_author(self, topic: dict[object, object]) -> str:
        for key in ("talk", "question"):
            section = topic.get(key, {})
            if not isinstance(section, dict):
                continue
            owner = section.get("owner", {})
            if isinstance(owner, dict):
                name = str(owner.get("name", "")).strip()
                if name:
                    return name
        return ""

    def _extract_stock_codes(self, text: str) -> list[str]:
        seen: set[str] = set()
        codes: list[str] = []
        for code in re.findall(r"\b\d{6}\b", text):
            if code not in seen:
                seen.add(code)
                codes.append(code)
        return codes
