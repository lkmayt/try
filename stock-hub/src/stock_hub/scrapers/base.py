from __future__ import annotations

# pyright: reportUnnecessaryIsInstance=false

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Protocol


logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all Stock Hub scrapers."""

    source_name: str

    @abstractmethod
    async def fetch_latest(self, limit: int = 30) -> list[object]:
        """Fetch the latest posts from this source."""

    @abstractmethod
    async def search(self, keyword: str, limit: int = 30) -> list[object]:
        """Search posts from this source by keyword."""

    async def scrape_and_store(self, db: "SupportsInsertPost") -> int:
        """Fetch latest posts, persist them, and return the count of new rows."""

        posts: Sequence[object] = await self.fetch_latest()
        new_count = 0
        for post in posts:
            result = db.insert_post(post)
            if result is not None:
                new_count += 1
        return new_count


class SupportsInsertPost(Protocol):
    def insert_post(self, post: object) -> object | None:
        """Persist a post-like object and return a truthy/new marker."""


class ScraperRegistry:
    """Registry for scraper instances keyed by source name."""

    def __init__(self) -> None:
        self._scrapers: dict[str, BaseScraper] = {}

    def register(self, scraper: BaseScraper) -> None:
        self._scrapers[scraper.source_name] = scraper

    def get(self, source_name: str) -> BaseScraper | None:
        return self._scrapers.get(source_name)

    def all(self) -> list[BaseScraper]:
        return list(self._scrapers.values())

    async def scrape_all(self, db: SupportsInsertPost) -> dict[str, int | Exception]:
        """Run all scrapers and isolate failures per source."""

        results: dict[str, int | Exception] = {}
        for name, scraper in self._scrapers.items():
            try:
                count = await scraper.scrape_and_store(db)
                results[name] = count
            except Exception as exc:  # pragma: no cover - exercised in tests
                logger.error("Scraper %s failed: %s", name, exc)
                results[name] = exc
        return results
