from __future__ import annotations

# pyright: reportAny=false

import json
from pathlib import Path
from typing import Any

import pytest

from stock_hub.scrapers.zsxq import ZsxqScraper


class DummyResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload: dict[str, Any] = payload
        self.status_code: int = status_code

    def json(self) -> dict[str, Any]:
        return self._payload


class DummyHttpClient:
    def __init__(self, responses: list[DummyResponse]) -> None:
        self.responses: list[DummyResponse] = responses
        self.calls: list[dict[str, Any]] = []

    async def get(self, url: str, **kwargs: Any) -> DummyResponse:
        self.calls.append({"url": url, **kwargs})
        return self.responses.pop(0)


@pytest.fixture()
def topics_payload() -> dict[str, Any]:
    return json.loads(Path(__file__).parent.joinpath("fixtures", "zsxq_topics.json").read_text(encoding="utf-8"))


def test_signature_generation() -> None:
    scraper = ZsxqScraper(config={"scrapers": {"zsxq": {}}})

    signature, timestamp = scraper._generate_signature(
        "/v2/groups",
        params={"count": "50"},
        timestamp="1714800000000",
    )

    assert timestamp == "1714800000000"
    assert signature == "e15f7ca37f6002b8845a73de05c8f93e"


def test_parse_topics(topics_payload: dict) -> None:
    scraper = ZsxqScraper(config={"scrapers": {"zsxq": {}}})

    posts = scraper._parse_topics(topics_payload, group_id="12345")

    assert len(posts) == 2
    assert all(post.source == "zsxq" for post in posts)
    assert posts[0].author == "投研达人"
    assert posts[0].stock_codes == ["600519", "688981"]
    assert posts[0].url == "https://wx.zsxq.com/group/12345/topic/123456"


def test_stock_code_extraction() -> None:
    scraper = ZsxqScraper(config={"scrapers": {"zsxq": {}}})
    text = "最新调研：贵州茅台(600519)Q1营收超预期。另外中芯国际(688981)产能利用率回升。"

    assert scraper._extract_stock_codes(text) == ["600519", "688981"]


@pytest.mark.asyncio()
async def test_cookie_expired_graceful(caplog: pytest.LogCaptureFixture) -> None:
    client = DummyHttpClient([DummyResponse({"succeeded": False}, status_code=401)])
    scraper = ZsxqScraper(
        http_client=client,
        config={"scrapers": {"zsxq": {"cookie": "zsxq_access_token=test", "group_ids": ["12345"]}}},
    )

    posts = await scraper.fetch_latest(limit=20)

    assert posts == []
    assert "知识星球 Cookie 已过期" in caplog.text


@pytest.mark.asyncio()
async def test_fetch_latest_parses_group_topics(topics_payload: dict) -> None:
    client = DummyHttpClient([DummyResponse(topics_payload)])
    scraper = ZsxqScraper(
        http_client=client,
        config={"scrapers": {"zsxq": {"cookie": "zsxq_access_token=test", "group_ids": ["12345"]}}},
    )

    posts = await scraper.fetch_latest(limit=2)

    assert len(posts) == 2
    assert client.calls[0]["headers"]["Cookie"] == "zsxq_access_token=test"
    assert client.calls[0]["headers"]["Origin"] == "https://wx.zsxq.com"
