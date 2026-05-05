from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportAny=false, reportExplicitAny=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from contextlib import asynccontextmanager
from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient

from stock_hub.api.app import app
from stock_hub.scrapers.base import BaseScraper
from stock_hub.storage.models import Post


@asynccontextmanager
async def started_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Any):
    config = {
        "server": {"host": "127.0.0.1", "port": 8000},
        "storage": {"db_path": str(tmp_path / "integration.db")},
        "scrapers": {
            "default_interval": 3600,
            "cninfo": {"enabled": True},
            "sse": {"enabled": True},
            "szse": {"enabled": True},
            "jiuyan": {"enabled": True},
            "zsxq": {"enabled": True},
        },
    }

    async def fake_scrape_and_store(self: BaseScraper, db: Any) -> int:
        _ = (self, db)
        return 0

    monkeypatch.setattr("stock_hub.api.app.get_config", lambda: config)
    monkeypatch.setattr(BaseScraper, "scrape_and_store", fake_scrape_and_store)

    async with app.router.lifespan_context(app):
        yield app


def make_client() -> AsyncClient:
    transport = ASGITransport(app=cast(Any, app))
    return AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_app_starts_and_health(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    async with started_app(monkeypatch, tmp_path):
        async with make_client() as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "sources" in payload


@pytest.mark.asyncio
async def test_search_after_insert(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    async with started_app(monkeypatch, tmp_path):
        app.state.db.insert_post(
            Post(
                source="cninfo",
                title="贵州茅台一季报",
                content="茅台收入和利润继续增长",
                author="测试作者",
                url="https://example.com/cninfo/mt-1",
                stock_codes=["600519"],
                published_at="2026-01-01T09:30:00",
                scraped_at="2026-01-01T09:35:00",
            )
        )

        async with make_client() as client:
            response = await client.get("/api/search", params={"q": "茅台"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert any(post["title"] == "贵州茅台一季报" for post in payload["results"])


@pytest.mark.asyncio
async def test_kline_endpoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    async with started_app(monkeypatch, tmp_path):
        async def fake_get_kline(*, code: str, frequency: str, count: int) -> list[dict[str, str | float]]:
            assert code == "600519"
            assert frequency == "daily"
            assert count == 2
            return [
                {
                    "time": "2026-01-02",
                    "open": 1660.0,
                    "high": 1680.0,
                    "low": 1655.0,
                    "close": 1675.0,
                    "volume": 1000.0,
                }
            ]

        app.state.quote_provider.get_kline = fake_get_kline

        async with make_client() as client:
            response = await client.get("/api/stocks/600519/kline", params={"count": 2})

    assert response.status_code == 200
    assert response.json() == {
        "candles": [
            {
                "time": "2026-01-02",
                "open": 1660.0,
                "high": 1680.0,
                "low": 1655.0,
                "close": 1675.0,
                "volume": 1000.0,
            }
        ]
    }


@pytest.mark.asyncio
async def test_scheduler_start_stop(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    async with started_app(monkeypatch, tmp_path):
        assert app.state.scheduler.running is True

        async with make_client() as client:
            stop_response = await client.post("/api/scheduler/stop")
            assert stop_response.status_code == 200
            assert app.state.scheduler.running is False

            start_response = await client.post("/api/scheduler/start")

        assert start_response.status_code == 200
        assert app.state.scheduler.running is True
