from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportAny=false, reportUnknownMemberType=false, reportImplicitOverride=false

import asyncio
import time
from unittest.mock import AsyncMock

import httpx
import pytest

from stock_hub.scrapers.base import BaseScraper, ScraperRegistry
from stock_hub.scrapers.http_client import HttpClient
from stock_hub.scrapers.rate_limiter import RateLimiter


class DummyScraper(BaseScraper):
    def __init__(self, source_name: str, posts: list[object] | None = None, error: Exception | None = None) -> None:
        self.source_name: str = source_name
        self._posts: list[object] = posts or []
        self._error: Exception | None = error

    async def fetch_latest(self, limit: int = 30) -> list[object]:
        if self._error is not None:
            raise self._error
        return self._posts[:limit]

    async def search(self, keyword: str, limit: int = 30) -> list[object]:
        return self._posts[:limit]


class DummyDb:
    def __init__(self, duplicate_indexes: set[int] | None = None) -> None:
        self.duplicate_indexes: set[int] = duplicate_indexes or set()
        self.insert_calls: int = 0

    def insert_post(self, post: object) -> object | None:
        index = self.insert_calls
        self.insert_calls += 1
        if index in self.duplicate_indexes:
            return None
        return post


@pytest.mark.asyncio
async def test_scraper_registry_register_and_get() -> None:
    registry = ScraperRegistry()
    scraper = DummyScraper("mock-source")

    registry.register(scraper)

    assert registry.get("mock-source") is scraper


def test_scraper_registry_all() -> None:
    registry = ScraperRegistry()
    scrapers = [DummyScraper(f"source-{i}") for i in range(3)]

    for scraper in scrapers:
        registry.register(scraper)

    assert registry.all() == scrapers


@pytest.mark.asyncio
async def test_scrape_all_isolates_failures() -> None:
    registry = ScraperRegistry()
    ok_scraper = DummyScraper("ok", posts=[{"id": 1}, {"id": 2}])
    bad_scraper = DummyScraper("bad", error=RuntimeError("boom"))
    db = DummyDb()

    registry.register(ok_scraper)
    registry.register(bad_scraper)

    results = await registry.scrape_all(db)

    assert results["ok"] == 2
    assert isinstance(results["bad"], RuntimeError)
    assert str(results["bad"]) == "boom"


@pytest.mark.asyncio
async def test_rate_limiter_throttles() -> None:
    limiter = RateLimiter(rate=2.0, burst=1)
    started = time.monotonic()

    for _ in range(5):
        await limiter.acquire()

    elapsed = time.monotonic() - started
    assert elapsed >= 2.0


@pytest.mark.asyncio
async def test_http_client_retries_on_500(monkeypatch: pytest.MonkeyPatch) -> None:
    client = HttpClient(max_retries=3)
    response_sequence = [
        httpx.Response(500, request=httpx.Request("GET", "https://example.com")),
        httpx.Response(502, request=httpx.Request("GET", "https://example.com")),
        httpx.Response(200, request=httpx.Request("GET", "https://example.com")),
    ]
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False
    mock_client.request = AsyncMock(side_effect=response_sequence)
    sleep_mock = AsyncMock()

    monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr(asyncio, "sleep", sleep_mock)

    response = await client.get("https://example.com")

    assert response.status_code == 200
    assert mock_client.request.await_count == 3
    assert sleep_mock.await_args_list == [((1,), {}), ((2,), {})]


@pytest.mark.asyncio
async def test_http_client_retries_on_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = HttpClient(max_retries=3)
    request = httpx.Request("GET", "https://example.com")
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False
    mock_client.request = AsyncMock(
        side_effect=[
            httpx.ConnectError("connect failed", request=request),
            httpx.Response(200, request=request),
        ]
    )
    sleep_mock = AsyncMock()

    monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr(asyncio, "sleep", sleep_mock)

    response = await client.get("https://example.com")

    assert response.status_code == 200
    assert mock_client.request.await_count == 2
    assert sleep_mock.await_args_list == [((1,), {})]


@pytest.mark.asyncio
async def test_scrape_and_store_counts_new() -> None:
    scraper = DummyScraper("mock-source", posts=[{"id": 1}, {"id": 2}, {"id": 3}])
    db = DummyDb(duplicate_indexes={1})

    count = await scraper.scrape_and_store(db)

    assert count == 2
    assert db.insert_calls == 3
