from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportExplicitAny=false, reportInvalidCast=false

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from typing import cast

from stock_hub.scheduler.keyword_matcher import match_keywords
from stock_hub.scheduler.status import SourceStatus
from stock_hub.scheduler.sync_state import save_sync_state, should_catch_up
from stock_hub.scrapers.base import BaseScraper, ScraperRegistry
from stock_hub.storage.database import Database


AlertCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class ScrapeScheduler:
    def __init__(self, db: Database, registry: ScraperRegistry, config: dict[str, Any]) -> None:
        self.db: Database = db
        self.registry: ScraperRegistry = registry
        self.config: dict[str, Any] = config
        self._statuses: dict[str, SourceStatus] = {
            scraper.source_name: SourceStatus(source_name=scraper.source_name)
            for scraper in self.registry.all()
        }
        self._tasks: list[asyncio.Task[None]] = []
        self.running: bool = False
        self._alert_callback: AlertCallback | None = None

    async def start(self) -> None:
        if self.running:
            return

        self.running = True
        self._tasks = []
        for scraper in self.registry.all():
            interval = self._get_interval(scraper.source_name)
            task = asyncio.create_task(
                self._run_scraper_loop(scraper, interval),
                name=f"scrape-{scraper.source_name}",
            )
            self._tasks.append(task)

    async def stop(self) -> None:
        self.running = False
        tasks = list(self._tasks)
        for task in tasks:
            _ = task.cancel()
        if tasks:
            _ = await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks = []

    def get_statuses(self) -> dict[str, SourceStatus]:
        return dict(self._statuses)

    def set_alert_callback(self, callback: AlertCallback | None) -> None:
        self._alert_callback = callback

    def _get_interval(self, source_name: str) -> int | float:
        scrapers_config = cast(dict[str, Any], self.config.get("scrapers", {}))
        default_interval = cast(int | float, scrapers_config.get("default_interval", 60))
        source_config = cast(dict[str, Any], scrapers_config.get(source_name, {}))
        return cast(int | float, source_config.get("interval", default_interval))

    async def _run_scraper_loop(self, scraper: BaseScraper, interval: int | float) -> None:
        log = logging.getLogger(f"scheduler.{scraper.source_name}")
        first_run = True
        while self.running:
            try:
                # Catch-up on first run if we've been offline for too long
                if first_run and should_catch_up(scraper.source_name, int(interval)):
                    log.info("gap detected — starting catch-up")
                    count = await self._catch_up_scraper(scraper, log)
                    log.info("catch-up completed: %d new posts", count)
                else:
                    count = await scraper.scrape_and_store(cast(Any, self.db))
                    log.info("scraped: %d new posts", count)
                
                first_run = False
                self._statuses[scraper.source_name] = SourceStatus(
                    source_name=scraper.source_name,
                    status="active",
                    last_scrape_time=datetime.now(UTC).isoformat(),
                    post_count=count,
                )
                save_sync_state(scraper.source_name)
                if count > 0:
                    await self._check_keywords(scraper.source_name)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("scrape failed: %s", exc)
                self._statuses[scraper.source_name] = SourceStatus(
                    source_name=scraper.source_name,
                    status="error",
                    error_message=str(exc),
                )
            await asyncio.sleep(interval)

    async def _catch_up_scraper(self, scraper: BaseScraper, log: logging.Logger, max_pages: int = 10) -> int:
        """Paginate through recent posts until we hit already-seen data."""
        total_new = 0
        for page in range(1, max_pages + 1):
            try:
                # Use a larger limit for catch-up
                posts = await scraper.fetch_latest(limit=50)
                if not posts:
                    break
                new = 0
                for post in posts:
                    if self.db.insert_post(post) is not None:
                        new += 1
                total_new += new
                log.info("catch-up page %d: %d new (total=%d)", page, new, total_new)
                if new == 0:
                    break  # All posts already in DB — caught up
            except Exception:
                break
        return total_new

    async def _check_keywords(self, source_name: str, limit: int = 50) -> None:
        posts = self.db.get_recent_posts(source=source_name, limit=limit)
        keywords = [str(item["keyword"]) for item in self.db.get_keywords()]
        if not keywords or self._alert_callback is None:
            return

        for post in posts:
            matches = match_keywords(post.title, post.content, keywords)
            if not matches:
                continue

            payload = {
                "source_name": source_name,
                "post_id": post.id,
                "title": post.title,
                "url": post.url,
                "matched_keywords": matches,
            }
            result = self._alert_callback(payload)
            if asyncio.iscoroutine(result):
                await result
