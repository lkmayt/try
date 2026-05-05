from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportAny=false, reportExplicitAny=false

import asyncio
from dataclasses import asdict, dataclass
from typing import Any, cast

from stock_hub.quotes.stock_info import get_exchange, get_stock_name

# Cache — mootdx bestip is slow, only do it once
_BESTIP_SCANNED = False
_BESTIP_LOCK = asyncio.Lock()


@dataclass(slots=True)
class Quote:
    code: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: float
    amount: float
    high: float
    low: float
    open: float
    prev_close: float


@dataclass(slots=True)
class Candle:
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class QuoteProvider:
    async def get_realtime_quote(self, code: str) -> Quote:
        try:
            return await self._mootdx_quote(code)
        except Exception:
            return await self._tencent_quote(code)

    async def get_batch_quotes(self, codes: list[str]) -> list[Quote]:
        quotes = await asyncio.gather(*(self.get_realtime_quote(code) for code in codes))
        return list(quotes)

    async def get_kline(
        self,
        code: str,
        frequency: str = "daily",
        count: int = 200,
    ) -> list[dict[str, Any]]:
        if frequency != "daily":
            raise ValueError(f"Unsupported frequency: {frequency}")

        # Try mootdx first (fastest when server is available)
        try:
            client = await self._get_mootdx_client()
            market = self._market_for_code(code)
            raw_bars = await asyncio.to_thread(self._load_bars, client, code, count, market)
            records = self._records_from_frame(raw_bars)
            if records:
                candles: list[dict[str, Any]] = []
                for row in records:
                    candle = Candle(
                        time=self._normalize_time(row.get("datetime") or row.get("date") or row.get("time")),
                        open=self._to_float(row.get("open")),
                        high=self._to_float(row.get("high")),
                        low=self._to_float(row.get("low")),
                        close=self._to_float(row.get("close")),
                        volume=self._to_float(row.get("volume") or row.get("vol")),
                    )
                    candles.append(asdict(candle))
                if candles:
                    return candles
        except Exception:
            pass

        # Fallback to akshare (slower but more reliable)
        try:
            import akshare as ak  # type: ignore
            df = await asyncio.wait_for(
                asyncio.to_thread(ak.stock_zh_a_hist, symbol=code, period="daily", adjust="qfq"),
                timeout=15,
            )
            if df is not None and not df.empty:
                records = df.tail(count).to_dict(orient="records")
                candles: list[dict[str, Any]] = []
                for row in records:
                    candle = Candle(
                        time=str(row.get("日期", "")),
                        open=self._to_float(row.get("开盘")),
                        high=self._to_float(row.get("最高")),
                        low=self._to_float(row.get("最低")),
                        close=self._to_float(row.get("收盘")),
                        volume=self._to_float(row.get("成交量")),
                    )
                    candles.append(asdict(candle))
                if candles:
                    return candles
        except Exception:
            pass

        # Last resort: return empty with comment
        return [{"time": "?", "open": 0, "high": 0, "low": 0, "close": 0, "volume": 0, "_error": "kline data unavailable"}]

    async def _get_mootdx_client(self) -> Any:
        """Get a mootdx client, scanning bestip only once."""
        global _BESTIP_SCANNED
        async with _BESTIP_LOCK:
            use_bestip = not _BESTIP_SCANNED
            if use_bestip:
                _BESTIP_SCANNED = True
            from mootdx.quotes import Quotes
            return cast(Any, Quotes.factory(market="std", bestip=use_bestip, timeout=10))

    async def _mootdx_quote(self, code: str) -> Quote:
        client = await self._get_mootdx_client()
        raw_quote = await asyncio.to_thread(self._load_quotes, client, code)
        records = self._records_from_frame(raw_quote)
        if not records:
            raise ValueError(f"No mootdx quote found for {code}")
        return self._quote_from_record(records[0], code)

    async def _tencent_quote(self, code: str) -> Quote:
        import easyquotation

        quotation = easyquotation.use("tencent")
        data = await asyncio.to_thread(self._load_tencent_quotes, quotation, code)
        record = cast(dict[str, Any] | None, data.get(code))
        if record is None:
            raise ValueError(f"No tencent quote found for {code}")
        return self._quote_from_record(record, code)

    def _load_quotes(self, client: Any, code: str) -> Any:
        return client.quotes(symbol=[code])

    def _load_bars(self, client: Any, code: str, count: int, market: int) -> Any:
        return client.bars(symbol=code, frequency=9, offset=0, count=count, market=market)

    def _load_tencent_quotes(self, quotation: Any, code: str) -> dict[str, Any]:
        data = quotation.real([code])
        if not isinstance(data, dict):
            raise TypeError("Unsupported tencent quote response type")
        return cast(dict[str, Any], data)

    def _quote_from_record(self, record: dict[str, Any], fallback_code: str) -> Quote:
        code = str(record.get("code") or record.get("symbol") or fallback_code)
        name = str(record.get("name") or get_stock_name(code))
        price = self._to_float(record.get("price") or record.get("now") or record.get("last_close"))
        prev_close = self._to_float(record.get("last_close") or record.get("close") or record.get("pre_close"))
        change = self._to_float(record.get("change") or (price - prev_close))
        change_pct_value = record.get("change_pct") or record.get("percent") or record.get("percentage")
        change_pct = self._to_float(change_pct_value if change_pct_value is not None else self._safe_pct(change, prev_close))

        return Quote(
            code=code,
            name=name,
            price=price,
            change=change,
            change_pct=change_pct,
            volume=self._to_float(record.get("volume") or record.get("vol")),
            amount=self._to_float(record.get("amount") or record.get("turnover")),
            high=self._to_float(record.get("high") or price),
            low=self._to_float(record.get("low") or price),
            open=self._to_float(record.get("open") or prev_close),
            prev_close=prev_close,
        )

    def _records_from_frame(self, data: Any) -> list[dict[str, Any]]:
        if hasattr(data, "to_dict"):
            return cast(list[dict[str, Any]], data.to_dict(orient="records"))
        if isinstance(data, list):
            return [cast(dict[str, Any], item) for item in data]
        raise TypeError("Unsupported quote response type")

    def _normalize_time(self, value: Any) -> str:
        text = str(value)
        return text[:10]

    def _market_for_code(self, code: str) -> int:
        return 1 if get_exchange(code) == "sh" else 0

    def _to_float(self, value: Any) -> float:
        if value in (None, ""):
            return 0.0
        return float(value)

    def _safe_pct(self, change: float, prev_close: float) -> float:
        if prev_close == 0:
            return 0.0
        return change / prev_close * 100
