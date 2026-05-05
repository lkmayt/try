"""Popularity/hot stock rankings from multiple sources (雪球 + 东方财富)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, cast

from stock_hub.config import get_config
from stock_hub.scrapers.http_client import HttpClient

logger = logging.getLogger(__name__)


@dataclass
class HotStock:
    rank: int
    code: str
    name: str
    price: float
    change_pct: float = 0.0
    hot_value: int = 0  # 热度值 (xueqiu-specific)
    source: str = ""


class HotRankProvider:
    """Fetches hot stock rankings from multiple sources."""

    def __init__(self, client: HttpClient | None = None) -> None:
        self.client = client or HttpClient()

    # ── 东方财富 人气榜 (no auth required) ──────────────────────────

    async def fetch_eastmoney(self) -> list[HotStock]:
        """东方财富个股人气榜 — 100 stocks, no authentication needed."""
        try:
            import akshare as ak  # type: ignore
            df = await asyncio.to_thread(ak.stock_hot_rank_em)
        except Exception as exc:
            logger.warning("Eastmoney hot rank failed: %s", exc)
            return []

        if df is None or df.empty:
            return []

        results: list[HotStock] = []
        for _, row in df.iterrows():
            try:
                results.append(HotStock(
                    rank=int(row.get("当前排名", row.get("rank", 0))),
                    code=self._clean_code(str(row.get("代码", ""))),
                    name=str(row.get("股票名称", row.get("name", ""))),
                    price=float(row.get("最新价", row.get("price", 0)) or 0),
                    change_pct=float(row.get("涨跌幅", row.get("change_pct", 0)) or 0),
                    source="eastmoney",
                ))
            except (ValueError, TypeError):
                continue

        return results

    # ── 雪球 人气榜 (requires cookie) ───────────────────────────────

    async def fetch_xueqiu(self, page_size: int = 50) -> list[HotStock]:
        """雪球沪深人气榜 — needs xq_a_token cookie configured."""
        config = get_config()
        scrapers_cfg = config.get("scrapers", {})
        xueqiu_cfg = scrapers_cfg.get("xueqiu", {}) if isinstance(scrapers_cfg, dict) else {}
        token = xueqiu_cfg.get("cookie", "") if isinstance(xueqiu_cfg, dict) else ""

        if not token:
            logger.info("Xueqiu: no cookie configured, skipping")
            return []

        try:
            results = await self._fetch_xueqiu_api(token, page_size)
        except Exception as exc:
            logger.warning("Xueqiu hot rank failed: %s", exc)
            return []

        return results

    async def _fetch_xueqiu_api(self, token: str, page_size: int) -> list[HotStock]:
        url = "https://stock.xueqiu.com/v5/stock/hot_stock/list.json"
        params = {
            "page": "1",
            "size": str(page_size),
            "order": "desc",
            "order_by": "value",
            "type": "12",  # 12 = 沪深
            "_": str(int(time.time() * 1000)),
            "x": "0.5",
        }
        headers = {
            "Referer": "https://xueqiu.com/",
            "Accept": "application/json",
        }
        cookies = {"xq_a_token": token}

        resp = await self.client.get(url, params=params, headers=headers, cookies=cookies)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("items", [])

        results: list[HotStock] = []
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            try:
                results.append(HotStock(
                    rank=i + 1,
                    code=self._clean_code(str(item.get("symbol", ""))),
                    name=str(item.get("name", "")),
                    price=float(item.get("current", 0) or 0),
                    change_pct=float(item.get("percent", 0) or 0),
                    hot_value=int(item.get("value", 0) or 0),
                    source="xueqiu",
                ))
            except (ValueError, TypeError):
                continue

        return results

    # ── Aggregate ───────────────────────────────────────────────────

    async def fetch_all(self) -> dict[str, list[HotStock]]:
        """Fetch from all configured sources in parallel."""
        eastmoney, xueqiu = await asyncio.gather(
            self.fetch_eastmoney(),
            self.fetch_xueqiu(),
        )
        result: dict[str, list[HotStock]] = {}
        if eastmoney:
            result["eastmoney"] = eastmoney
        if xueqiu:
            result["xueqiu"] = xueqiu
        return result

    def _clean_code(self, code: str) -> str:
        """Normalize stock code: strip exchange prefix (SH/SZ/BJ)."""
        return re.sub(r"^(SH|SZ|BJ)", "", code.strip().upper())

    async def close(self) -> None:
        await self.client.close()
