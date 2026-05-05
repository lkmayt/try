from __future__ import annotations

from pathlib import Path

import pytest

from stock_hub.scrapers.szse_interactive import SZSEInteractiveScraper


class DummyResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class DummyHttpClient:
    def __init__(self, html: str) -> None:
        self.html = html
        self.urls: list[str] = []

    async def get(self, url: str, **kwargs):
        self.urls.append(url)
        return DummyResponse(self.html)


@pytest.fixture()
def fixture_html() -> str:
    return Path(__file__).parent.joinpath("fixtures", "szse_response.html").read_text(encoding="utf-8")


@pytest.mark.asyncio()
async def test_fetch_latest_returns_empty():
    """SZSE has no general feed — fetch_latest returns empty by design."""
    scraper = SZSEInteractiveScraper(http_client=DummyHttpClient("<html></html>"), use_akshare=False)
    posts = await scraper.fetch_latest()
    assert posts == []


@pytest.mark.asyncio()
async def test_search_http_fallback(fixture_html):
    """search() with a stock code uses HTTP fallback when akshare disabled."""
    scraper = SZSEInteractiveScraper(http_client=DummyHttpClient(fixture_html), use_akshare=False)
    posts = await scraper.search("000001", limit=10)

    assert len(posts) == 2
    assert posts[0].author == "平安银行"
    assert posts[0].published_at == "2026-04-18"


@pytest.mark.asyncio()
async def test_search_by_stock_code(fixture_html):
    """search() filters by 6-digit stock code and returns results."""
    scraper = SZSEInteractiveScraper(http_client=DummyHttpClient(fixture_html), use_akshare=False)

    posts = await scraper.search("000001", limit=1)

    assert len(posts) == 1
    assert posts[0].source == "szse"
    assert posts[0].published_at == "2026-04-18"


@pytest.mark.asyncio()
async def test_search_non_stock_code_returns_empty(fixture_html):
    """search() with non-stock-code keyword returns empty list."""
    scraper = SZSEInteractiveScraper(http_client=DummyHttpClient(fixture_html), use_akshare=False)

    posts = await scraper.search("not_a_code")

    assert posts == []
