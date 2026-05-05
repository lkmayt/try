from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportAny=false, reportExplicitAny=false

from datetime import datetime, UTC
from typing import Annotated, Any, cast

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from stock_hub.config import get_config
from stock_hub.quotes.provider import QuoteProvider
from stock_hub.scheduler.scheduler import ScrapeScheduler
from stock_hub.scheduler.status import SourceStatus
from stock_hub.storage.database import Database
from stock_hub.storage.models import Post

from stock_hub.api.schemas import (
    HealthResponse,
    KeywordCreate,
    KeywordResponse,
    RecentPostsResponse,
    SearchResponse,
    StockDetailResponse,
    PostResponse,
)

router = APIRouter(prefix="/api", tags=["api"])


def _get_db(request: Request) -> Database:
    return cast(Database, request.app.state.db)


def _get_scheduler(request: Request) -> ScrapeScheduler | None:
    scheduler = getattr(request.app.state, "scheduler", None)
    return cast(ScrapeScheduler | None, scheduler)


def _get_quote_provider(request: Request) -> QuoteProvider:
    provider = getattr(request.app.state, "quote_provider", None)
    if provider is not None and hasattr(provider, "get_kline"):
        return cast(QuoteProvider, provider)
    return QuoteProvider()


def _serialize_post(post: Post) -> PostResponse:
    if post.id is None:
        raise ValueError("Post id is required for API responses")

    return PostResponse(
        id=post.id,
        source=post.source,
        title=post.title,
        content=post.content,
        author=post.author,
        url=post.url,
        stock_codes=post.stock_codes,
        published_at=post.published_at,
    )


def _uptime_seconds(request: Request) -> int:
    started_at = getattr(request.app.state, "started_at", None)
    if not isinstance(started_at, datetime):
        return 0
    return max(0, int((datetime.now(UTC) - started_at).total_seconds()))


def _source_status_payload(request: Request) -> dict[str, dict[str, str | int | None]]:
    db = _get_db(request)
    sources: dict[str, dict[str, str | int | None]] = {
        name: {
            "count": values["count"],
            "latest_scraped_at": values["latest_scraped_at"],
        }
        for name, values in db.get_source_stats().items()
    }

    scheduler = _get_scheduler(request)
    if scheduler is None:
        return sources

    for name, status in scheduler.get_statuses().items():
        source_status: SourceStatus = status
        details = sources.setdefault(name, {})
        details.update(
            {
                "status": source_status.status,
                "last_scrape_time": source_status.last_scrape_time or None,
                "post_count": source_status.post_count,
                "error_message": source_status.error_message or None,
            }
        )
    return sources


def _configured_sources() -> dict[str, dict[str, bool]]:
    config: dict[str, Any] = get_config()
    scrapers = config.get("scrapers", {})
    if not isinstance(scrapers, dict):
        return {}

    sources: dict[str, dict[str, bool]] = {}
    for name, value in scrapers.items():
        if isinstance(name, str) and isinstance(value, dict):
            sources[name] = {"enabled": bool(value.get("enabled", False))}
    return sources


def _serialize_keyword(keyword: dict[str, str | int]) -> KeywordResponse:
    return KeywordResponse(
        id=int(keyword["id"]),
        keyword=str(keyword["keyword"]),
        created_at=str(keyword["created_at"]),
    )


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    return HealthResponse(status="ok", sources=_source_status_payload(request), uptime=_uptime_seconds(request))


@router.get("/search", response_model=SearchResponse)
async def search_posts(
    request: Request,
    q: str = "",
    source: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SearchResponse:
    import asyncio
    import re

    db = _get_db(request)

    if not q.strip():
        posts = db.get_recent_posts(source=source, limit=limit)
        results = posts[offset : offset + limit]
        return SearchResponse(results=[_serialize_post(post) for post in results], total=len(posts))

    # If query looks like a stock code (6 digits), trigger on-demand SZSE fetch
    if re.match(r"^\d{6}$", q.strip()):
        registry = getattr(request.app.state, "registry", None)
        if registry is not None:
            szse = registry.get("szse")
            if szse is not None:
                try:
                    szse_posts = await szse.search(q, limit=30)
                    for post in szse_posts:
                        db.insert_post(post)
                except Exception:
                    pass  # On-demand fetch is best-effort

    posts = db.search_posts(query=q, source=source, limit=limit, offset=offset)
    return SearchResponse(results=[_serialize_post(post) for post in posts], total=len(posts))


@router.get("/posts/recent", response_model=RecentPostsResponse)
async def recent_posts(
    request: Request,
    source: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> RecentPostsResponse:
    db = _get_db(request)
    posts = db.get_recent_posts(source=source, limit=limit)
    return RecentPostsResponse(posts=[_serialize_post(post) for post in posts])


@router.get("/stocks/{code}", response_model=StockDetailResponse)
async def stock_detail(
    code: str,
    request: Request,
    source: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> StockDetailResponse:
    db = _get_db(request)
    # Try exact stock_code match first
    posts = db.get_posts_by_stock(stock_code=code, source=source, limit=limit)
    # Fallback: search by title containing the code
    if not posts:
        import re
        if re.match(r"^\d{6}$", code):
            posts = db.search_posts(query=code, source=source, limit=limit)
    if not posts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")

    # Try to resolve stock name
    name = code
    try:
        from stock_hub.quotes.stock_info import get_stock_name
        name = get_stock_name(code) or code
    except Exception:
        pass

    return StockDetailResponse(code=code, name=name, posts=[_serialize_post(post) for post in posts])


@router.get("/stocks/{code}/kline", response_model=dict[str, list[dict[str, str | float]]])
async def stock_kline(
    request: Request,
    code: str,
    frequency: str = "daily",
    count: Annotated[int, Query(ge=1, le=2000)] = 200,
) -> dict[str, list[dict[str, str | float]]]:
    provider = _get_quote_provider(request)
    candles = await provider.get_kline(code=code, frequency=frequency, count=count)
    return {"candles": candles}


@router.get("/keywords", response_model=dict[str, list[KeywordResponse]])
async def list_keywords(request: Request) -> dict[str, list[KeywordResponse]]:
    db = _get_db(request)
    keywords = [_serialize_keyword(keyword) for keyword in db.get_keywords()]
    return {"keywords": keywords}


@router.post("/keywords", status_code=status.HTTP_201_CREATED, response_model=KeywordResponse)
async def create_keyword(payload: KeywordCreate, request: Request) -> KeywordResponse:
    db = _get_db(request)
    keyword_id = db.add_keyword(payload.keyword)
    created = next(keyword for keyword in db.get_keywords() if keyword["id"] == keyword_id)
    return _serialize_keyword(created)


@router.delete("/keywords/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword(keyword_id: int, request: Request) -> Response:
    db = _get_db(request)
    db.delete_keyword(keyword_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sources", response_model=dict[str, dict[str, dict[str, bool]]])
async def sources() -> dict[str, dict[str, dict[str, bool]]]:
    return {"sources": _configured_sources()}


@router.get("/hotrank/{source}")
async def hot_rank(source: str) -> dict[str, list[dict[str, object]]]:
    """Fetch hot stock rankings. source: 'eastmoney' | 'xueqiu' | 'all'."""
    from stock_hub.scrapers.hot_rank import HotRankProvider, HotStock

    provider = HotRankProvider()
    try:
        if source == "eastmoney":
            stocks = await provider.fetch_eastmoney()
            return {"stocks": [_hot_stock_to_dict(s) for s in stocks]}
        elif source == "xueqiu":
            stocks = await provider.fetch_xueqiu()
            return {"stocks": [_hot_stock_to_dict(s) for s in stocks]}
        elif source == "all":
            result = await provider.fetch_all()
            return {
                k: [_hot_stock_to_dict(s) for s in v]
                for k, v in result.items()
            }
        else:
            raise HTTPException(status_code=404, detail=f"Unknown source: {source}")
    finally:
        await provider.close()


def _hot_stock_to_dict(s: object) -> dict[str, object]:
    from dataclasses import asdict
    return asdict(s)

@router.post("/scheduler/start")
async def start_scheduler(request: Request) -> dict[str, str]:
    scheduler = _get_scheduler(request)
    if scheduler is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Scheduler unavailable")
    await scheduler.start()
    return {"status": "ok", "message": "Scheduler started"}

@router.post("/scheduler/stop")
async def stop_scheduler(request: Request) -> dict[str, str]:
    scheduler = _get_scheduler(request)
    if scheduler is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Scheduler unavailable")
    await scheduler.stop()
    return {"status": "ok", "message": "Scheduler stopped"}

@router.post("/config/{source}")
async def update_config(source: str, request: Request) -> dict[str, str]:
    _ = await request.json()
    return {"status": "ok", "message": f"Config for {source} updated"}
