from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportAny=false, reportExplicitAny=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

from datetime import UTC, datetime
from collections.abc import Iterator
from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient

from stock_hub.api.app import app
from stock_hub.config import get_config
from stock_hub.storage.database import Database
from stock_hub.storage.models import Post


def make_post(
    *,
    source: str = "cninfo",
    title: str = "默认标题",
    content: str = "默认内容",
    author: str = "测试作者",
    url: str = "https://example.com/default",
    stock_codes: list[str] | None = None,
    published_at: str = "2026-01-01T09:30:00",
    scraped_at: str = "2026-01-01T09:35:00",
) -> Post:
    return Post(
        source=source,
        title=title,
        content=content,
        author=author,
        url=url,
        stock_codes=list(stock_codes or []),
        published_at=published_at,
        scraped_at=scraped_at,
    )


@pytest.fixture(autouse=True)
def api_database() -> Iterator[Database]:
    db = Database(":memory:")
    original_db = getattr(app.state, "db", None)
    original_started_at = getattr(app.state, "started_at", None)
    app.state.db = db
    app.state.started_at = datetime.now(UTC)
    try:
        yield db
    finally:
        db.close()
        if original_db is None:
            if hasattr(app.state, "db"):
                delattr(app.state, "db")
        else:
            app.state.db = original_db
        if original_started_at is None:
            if hasattr(app.state, "started_at"):
                delattr(app.state, "started_at")
        else:
            app.state.started_at = original_started_at


def make_client() -> AsyncClient:
    transport = ASGITransport(app=cast(Any, app))
    return AsyncClient(transport=transport, base_url="http://testserver")


def seed_posts(db: Database) -> None:
    posts = [
        make_post(
            source="cninfo",
            title="贵州茅台年度报告",
            content="茅台业绩继续增长，机构看好高端白酒。",
            url="https://example.com/cninfo-1",
            stock_codes=["600519"],
            scraped_at="2026-01-01T10:00:00",
        ),
        make_post(
            source="sse",
            title="上交所问询函回复",
            content="600519 公司回复交易所关于经营情况的问询。",
            url="https://example.com/sse-1",
            stock_codes=["600519"],
            scraped_at="2026-01-01T09:00:00",
        ),
        make_post(
            source="szse",
            title="宁德时代调研纪要",
            content="300750 新能源产业链景气度延续。",
            url="https://example.com/szse-1",
            stock_codes=["300750"],
            scraped_at="2026-01-01T08:00:00",
        ),
    ]
    for post in posts:
        db.insert_post(post)


@pytest.mark.asyncio
async def test_health_endpoint(api_database: Database) -> None:
    seed_posts(api_database)

    async with make_client() as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "sources" in payload
    assert "uptime" in payload


@pytest.mark.asyncio
async def test_search_chinese(api_database: Database) -> None:
    seed_posts(api_database)

    async with make_client() as client:
        response = await client.get("/api/search", params={"q": "茅台"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert any("茅台" in post["title"] or "茅台" in post["content"] for post in payload["results"])


@pytest.mark.asyncio
async def test_search_empty_query(api_database: Database) -> None:
    seed_posts(api_database)

    async with make_client() as client:
        response = await client.get("/api/search")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["results"][0]["title"] == "贵州茅台年度报告"


@pytest.mark.asyncio
async def test_search_with_source_filter(api_database: Database) -> None:
    seed_posts(api_database)

    async with make_client() as client:
        response = await client.get("/api/search", params={"q": "茅台", "source": "cninfo"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert all(post["source"] == "cninfo" for post in payload["results"])


@pytest.mark.asyncio
async def test_recent_posts(api_database: Database) -> None:
    seed_posts(api_database)

    async with make_client() as client:
        response = await client.get("/api/posts/recent")

    assert response.status_code == 200
    payload = response.json()
    assert [post["title"] for post in payload["posts"]] == [
        "贵州茅台年度报告",
        "上交所问询函回复",
        "宁德时代调研纪要",
    ]


@pytest.mark.asyncio
async def test_stock_detail(api_database: Database) -> None:
    seed_posts(api_database)

    async with make_client() as client:
        response = await client.get("/api/stocks/600519")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == "600519"
    assert payload["name"] == "600519"
    assert len(payload["posts"]) == 2


@pytest.mark.asyncio
async def test_stock_not_found() -> None:
    async with make_client() as client:
        response = await client.get("/api/stocks/999999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_keyword_crud() -> None:
    async with make_client() as client:
        create_response = await client.post("/api/keywords", json={"keyword": "半导体"})

        assert create_response.status_code == 201
        created = create_response.json()
        keyword_id = created["id"]
        assert created["keyword"] == "半导体"

        list_response = await client.get("/api/keywords")
        assert list_response.status_code == 200
        keywords = list_response.json()["keywords"]
        assert any(keyword["id"] == keyword_id and keyword["keyword"] == "半导体" for keyword in keywords)

        delete_response = await client.delete(f"/api/keywords/{keyword_id}")
        assert delete_response.status_code == 204

        list_after_delete = await client.get("/api/keywords")
        remaining = list_after_delete.json()["keywords"]
        assert all(keyword["id"] != keyword_id for keyword in remaining)


@pytest.mark.asyncio
async def test_sources_endpoint() -> None:
    async with make_client() as client:
        response = await client.get("/api/sources")

    assert response.status_code == 200
    payload = response.json()
    expected_sources = {
        name: values
        for name, values in get_config().get("scrapers", {}).items()
        if isinstance(values, dict)
    }
    assert set(payload["sources"]) == set(expected_sources)
    assert payload["sources"]["cninfo"]["enabled"] is True
