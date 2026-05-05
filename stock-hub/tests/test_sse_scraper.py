from __future__ import annotations

from pathlib import Path

import pytest

from stock_hub.scrapers.sse_interactive import SSEInteractiveScraper


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


class DummyHttpClient:
    def __init__(self, response: DummyResponse) -> None:
        self.response = response
        self.urls: list[str] = []
        self.last_data: dict[str, str] = {}

    async def get(self, url: str, **kwargs):
        self.urls.append(url)
        return self.response

    async def post(self, url: str, data: dict[str, str] | None = None, headers: dict[str, str] | None = None, **kwargs):
        self.urls.append(url)
        if data:
            self.last_data = data
        return self.response


@pytest.mark.asyncio
async def test_fetch_latest_parses_fixture_html() -> None:
    html = Path("tests/fixtures/sse_response.html").read_text(encoding="utf-8")
    scraper = SSEInteractiveScraper(http_client=DummyHttpClient(DummyResponse(html)), use_akshare=False)

    posts = await scraper.fetch_latest(limit=10)

    assert len(posts) == 2
    assert posts[0].source == "sse"
    assert posts[0].title == "请问公司2024年一季度业绩如何？"
    assert "公司2024年一季度实现营业收入100亿元" in posts[0].content
    assert posts[0].published_at == "2024-03-28 14:30"
    assert posts[0].url.endswith("feed_123")


@pytest.mark.asyncio
async def test_search_uses_http_and_keyword() -> None:
    html = Path("tests/fixtures/sse_response.html").read_text(encoding="utf-8")
    client = DummyHttpClient(DummyResponse(html))
    scraper = SSEInteractiveScraper(http_client=client, use_akshare=False)

    posts = await scraper.search("600000", limit=5)

    assert len(posts) == 2
    assert client.last_data.get("keyword") == "600000"


@pytest.mark.asyncio
async def test_fetch_latest_trims_to_limit() -> None:
    html = Path("tests/fixtures/sse_response.html").read_text(encoding="utf-8")
    scraper = SSEInteractiveScraper(http_client=DummyHttpClient(DummyResponse(html)), use_akshare=False)

    posts = await scraper.fetch_latest(limit=1)

    assert len(posts) == 1
    assert posts[0].author == "投资者张三"
