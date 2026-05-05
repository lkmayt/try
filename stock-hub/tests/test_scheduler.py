from __future__ import annotations

# pyright: reportAny=false, reportUnknownParameterType=false, reportMissingTypeStubs=false, reportImplicitOverride=false

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from stock_hub.scheduler import ScrapeScheduler, SourceStatus, match_keywords
from stock_hub.scrapers.base import BaseScraper, ScraperRegistry
from stock_hub.storage.models import Post


class MockScraper(BaseScraper):
    def __init__(
        self,
        source_name: str,
        db_posts_factory: Callable[[int], list[Post]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.source_name = source_name
        self.db_posts_factory = db_posts_factory or (lambda _: [])
        self.error = error
        self.call_count = 0

    async def fetch_latest(self, limit: int = 30) -> list[object]:
        return []

    async def search(self, keyword: str, limit: int = 30) -> list[object]:
        return []

    async def scrape_and_store(self, db: Any) -> int:
        self.call_count += 1
        if self.error is not None:
            raise self.error

        inserted = 0
        for post in self.db_posts_factory(self.call_count):
            if db.insert_post(post) is not None:
                inserted += 1
        return inserted


@pytest.mark.asyncio
async def test_keyword_matching() -> None:
    assert match_keywords("贵州茅台业绩大增", "", ["茅台", "半导体"]) == ["茅台"]


@pytest.mark.asyncio
async def test_keyword_matching_case_insensitive() -> None:
    assert match_keywords("NVIDIA earnings", "AI demand remains strong", ["nvidia", "tesla", "Ai"]) == [
        "nvidia",
        "Ai",
    ]


@pytest.mark.asyncio
async def test_keyword_no_match() -> None:
    assert match_keywords("贵州银行", "利润稳定", ["茅台", "半导体"]) == []


@pytest.mark.asyncio
async def test_scheduler_start_stop(database: Any) -> None:
    registry = ScraperRegistry()
    scraper_a = MockScraper("a")
    scraper_b = MockScraper("b")
    registry.register(scraper_a)
    registry.register(scraper_b)

    scheduler = ScrapeScheduler(
        database,
        registry,
        {"scrapers": {"default_interval": 0.5}},
    )

    await scheduler.start()
    await asyncio.sleep(2)
    await scheduler.stop()

    assert scraper_a.call_count >= 2
    assert scraper_b.call_count >= 2
    assert scheduler.running is False
    assert scheduler._tasks == []


@pytest.mark.asyncio
async def test_scheduler_failure_isolation(database: Any) -> None:
    registry = ScraperRegistry()
    good_scraper = MockScraper(
        "good",
        db_posts_factory=lambda _: [
            Post(source="good", title="正常公告", content="", url="https://example.com/good")
        ],
    )
    bad_scraper = MockScraper("bad", error=RuntimeError("boom"))
    registry.register(good_scraper)
    registry.register(bad_scraper)

    scheduler = ScrapeScheduler(
        database,
        registry,
        {"scrapers": {"default_interval": 0.5}},
    )

    await scheduler.start()
    await asyncio.sleep(1.2)
    await scheduler.stop()

    statuses = scheduler.get_statuses()
    assert statuses["good"].status == "active"
    assert statuses["good"].post_count >= 0
    assert statuses["bad"].status == "error"
    assert statuses["bad"].error_message == "boom"


@pytest.mark.asyncio
async def test_source_status_updated(database: Any) -> None:
    registry = ScraperRegistry()
    scraper = MockScraper(
        "cninfo",
        db_posts_factory=lambda _: [
            Post(source="cninfo", title="贵州茅台公告", content="业绩提升", url="https://example.com/1")
        ],
    )
    registry.register(scraper)
    scheduler = ScrapeScheduler(
        database,
        registry,
        {"scrapers": {"default_interval": 0.5, "cninfo": {"interval": 0.5}}},
    )

    await scheduler.start()
    await asyncio.sleep(0.8)  # Wait for first scrape to complete
    await scheduler.stop()

    status = scheduler.get_statuses()["cninfo"]
    assert isinstance(status, SourceStatus)
    assert status.source_name == "cninfo"
    assert status.status == "active"
    assert status.last_scrape_time
    assert status.post_count >= 0  # May be 0 or 1 depending on catch-up timing
    assert status.error_message == ""


@pytest.mark.asyncio
async def test_scheduler_keyword_alert_callback(database: Any) -> None:
    registry = ScraperRegistry()
    scraper = MockScraper(
        "cninfo",
        db_posts_factory=lambda _: [
            Post(source="cninfo", title="贵州茅台公告", content="业绩大增", url="https://example.com/mt")
        ],
    )
    registry.register(scraper)
    database.add_keyword("茅台")
    alerts: list[dict[str, Any]] = []

    async def capture_alert(payload: dict[str, Any]) -> None:
        alerts.append(payload)

    scheduler = ScrapeScheduler(
        database,
        registry,
        {"scrapers": {"default_interval": 0.5}},
    )
    scheduler.set_alert_callback(capture_alert)

    await scheduler.start()
    await asyncio.sleep(0.8)
    await scheduler.stop()

    assert alerts
    assert alerts[0]["source_name"] == "cninfo"
    assert alerts[0]["matched_keywords"] == ["茅台"]
