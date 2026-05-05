from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest
import httpx

from stock_hub.scrapers.jiuyangongshe import JiuyangongsheScraper
from stock_hub.scrapers.http_client import HttpClient
from stock_hub.storage.models import Post


COMMUNITY_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "jiuyan_community.json"
SEARCH_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "jiuyan_search.json"


def load_fixture(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class DummyHttpClient(HttpClient):
    def __init__(self, payload: dict[str, object]) -> None:
        super().__init__()
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    async def post(self, url: str, **kwargs) -> httpx.Response:
        self.calls.append({"url": url, **kwargs})
        request = httpx.Request("POST", url, json=kwargs.get("json"), headers=cast(dict[str, str], kwargs.get("headers", {})))
        return httpx.Response(200, json=self.payload, request=request)


def test_token_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    scraper = JiuyangongsheScraper()
    monkeypatch.setattr("stock_hub.scrapers.jiuyangongshe.time.time", lambda: 1714800000.0)

    headers = scraper._generate_auth_headers()

    expected = hashlib.md5("Uu0KfOB8iUP69d3c:1714800000000".encode()).hexdigest()
    assert headers == {
        "platform": "3",
        "timestamp": "1714800000000",
        "token": expected,
    }


def test_parse_community_response() -> None:
    scraper = JiuyangongsheScraper()
    payload = load_fixture(COMMUNITY_FIXTURE_PATH)

    posts = scraper._parse_posts(payload)

    assert len(posts) == 2
    assert all(isinstance(post, Post) for post in posts)
    assert posts[0].source == "jiuyan"
    assert posts[0].title == "茅台2024Q1业绩点评"
    assert posts[0].content == "贵州茅台2024年一季度营收同比增长15%..."
    assert posts[0].author == "研究员小王"
    assert posts[0].url == "https://www.jiuyangongshe.com/a/12345"
    assert posts[0].stock_codes == ["600519"]
    assert posts[0].published_at == "2024-03-28 14:30:00"


@pytest.mark.asyncio
async def test_fetch_latest_mock() -> None:
    payload = load_fixture(COMMUNITY_FIXTURE_PATH)
    client = DummyHttpClient(payload)
    scraper = JiuyangongsheScraper(client=client)

    posts = await scraper.fetch_latest(limit=30)

    assert len(posts) == 2
    call = client.calls[0]
    assert call["url"] == JiuyangongsheScraper.COMMUNITY_URL
    assert call["json"] == {
        "category_id": "",
        "limit": 30,
        "order": 0,
        "start": 1,
        "type": 0,
        "back_garden": 0,
    }
    headers = cast(dict[str, str], call["headers"])
    assert headers["platform"] == "3"
    assert headers["timestamp"]
    assert headers["token"]


@pytest.mark.asyncio
async def test_search_with_keyword() -> None:
    payload = load_fixture(SEARCH_FIXTURE_PATH)
    client = DummyHttpClient(payload)
    scraper = JiuyangongsheScraper(client=client)

    posts = await scraper.search("半导体", limit=5)

    assert len(posts) == 2
    assert posts[1].title == "半导体设备国产替代观察"
    call = client.calls[0]
    assert call["url"] == JiuyangongsheScraper.SEARCH_URL
    body = cast(dict[str, object], call["json"])
    assert body["keyword"] == "半导体"
    assert body["limit"] == 5
    assert body["start"] == 1
