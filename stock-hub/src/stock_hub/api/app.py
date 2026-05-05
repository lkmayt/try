from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportAny=false, reportExplicitAny=false

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from stock_hub.api.routes import router
from stock_hub.api.ws import manager, ws_router
from stock_hub.config import get_config
from stock_hub.storage.database import Database


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config: dict[str, Any] = get_config()

    storage = config.get("storage", {})
    db_path = storage.get("db_path", "stock_hub.db") if isinstance(storage, dict) else "stock_hub.db"
    db = Database(db_path)
    db.init_db()
    app.state.db = db

    from stock_hub.quotes.provider import QuoteProvider
    from stock_hub.scheduler.scheduler import ScrapeScheduler
    from stock_hub.scrapers.base import ScraperRegistry
    from stock_hub.scrapers.cninfo import CNInfoScraper
    from stock_hub.scrapers.jiuyangongshe import JiuyangongsheScraper
    from stock_hub.scrapers.sse_interactive import SSEInteractiveScraper
    from stock_hub.scrapers.szse_interactive import SZSEInteractiveScraper
    from stock_hub.scrapers.zsxq import ZsxqScraper

    registry = ScraperRegistry()
    registry.register(SSEInteractiveScraper(use_akshare=True))
    registry.register(SZSEInteractiveScraper(use_akshare=True))
    registry.register(CNInfoScraper())
    registry.register(JiuyangongsheScraper())
    registry.register(ZsxqScraper())
    app.state.registry = registry

    scheduler = ScrapeScheduler(db=db, registry=registry, config=config)
    app.state.scheduler = scheduler

    quote_provider = QuoteProvider()
    app.state.quote_provider = quote_provider
    manager.set_provider(quote_provider)

    async def emit_keyword_alert(payload: dict[str, Any]) -> None:
        matched_keywords = payload.get("matched_keywords", [])
        keywords = matched_keywords if isinstance(matched_keywords, list) else []
        for keyword in keywords:
            await manager.broadcast_alert(
                {
                    "type": "keyword_alert",
                    "keyword": str(keyword),
                    "matched_keywords": [str(item) for item in keywords],
                    "post": {
                        "id": payload.get("post_id"),
                        "title": str(payload.get("title", "")),
                        "url": str(payload.get("url", "")),
                        "source": str(payload.get("source_name", "")),
                    },
                }
            )

    scheduler.set_alert_callback(emit_keyword_alert)
    await scheduler.start()
    app.state.started_at = datetime.now(UTC)
    try:
        yield
    finally:
        await scheduler.stop()
        db.close()


app = FastAPI(title="Stock Hub API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://0.0.0.0:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(ws_router)
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
