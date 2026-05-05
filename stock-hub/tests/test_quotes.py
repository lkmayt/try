from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
import pytest

from stock_hub.quotes.provider import QuoteProvider
from stock_hub.quotes.stock_info import get_exchange


class FakeFrame:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self._records: list[dict[str, object]] = records

    def to_dict(self, *, orient: str) -> list[dict[str, object]]:
        assert orient == "records"
        return self._records


@pytest.mark.asyncio
async def test_quote_provider_mootdx(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeQuotesClient:
        def quotes(self, *, symbol: list[str]) -> FakeFrame:
            assert symbol == ["600519"]
            return FakeFrame(
                [
                    {
                        "code": "600519",
                        "name": "贵州茅台",
                        "price": 1688.0,
                        "last_close": 1660.0,
                        "change": 28.0,
                        "change_pct": 1.69,
                        "volume": 12345,
                        "amount": 9876543,
                        "high": 1690.0,
                        "low": 1650.0,
                        "open": 1668.0,
                    }
                ]
            )

    fake_quotes_module = ModuleType("mootdx.quotes")
    setattr(fake_quotes_module, "Quotes", SimpleNamespace(factory=lambda market, **kw: FakeQuotesClient()))
    monkeypatch.setitem(sys.modules, "mootdx.quotes", fake_quotes_module)

    provider = QuoteProvider()
    quote = await provider.get_realtime_quote("600519")

    assert quote.code == "600519"
    assert quote.name == "贵州茅台"
    assert quote.price == 1688.0
    assert quote.change_pct == 1.69


@pytest.mark.asyncio
async def test_quote_provider_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingQuotesClient:
        def quotes(self, *, symbol: list[str]) -> FakeFrame:
            _ = symbol
            raise RuntimeError("mootdx unavailable")

    class FakeQuotation:
        def real(self, codes: list[str]) -> dict[str, dict[str, object]]:
            assert codes == ["000001"]
            return {
                "000001": {
                    "code": "000001",
                    "name": "平安银行",
                    "now": 10.5,
                    "close": 10.0,
                    "volume": 2000,
                    "turnover": 21000,
                    "high": 10.8,
                    "low": 9.9,
                    "open": 10.1,
                }
            }

    fake_quotes_module = ModuleType("mootdx.quotes")
    setattr(fake_quotes_module, "Quotes", SimpleNamespace(factory=lambda market: FailingQuotesClient()))
    fake_easyquotation = ModuleType("easyquotation")
    setattr(fake_easyquotation, "use", lambda source: FakeQuotation())
    monkeypatch.setitem(sys.modules, "mootdx.quotes", fake_quotes_module)
    monkeypatch.setitem(sys.modules, "easyquotation", fake_easyquotation)

    provider = QuoteProvider()
    quote = await provider.get_realtime_quote("000001")

    assert quote.code == "000001"
    assert quote.name == "平安银行"
    assert quote.price == 10.5
    assert quote.change == 0.5
    assert quote.change_pct == 5.0


@pytest.mark.asyncio
async def test_kline_format(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeQuotesClient:
        def bars(self, *, symbol: str, frequency: int, offset: int, count: int, market: int) -> FakeFrame:
            assert symbol == "600519"
            assert frequency == 9
            assert offset == 0
            assert count == 2
            assert market == 1
            return FakeFrame(
                [
                    {
                        "datetime": "2026-01-02 00:00:00",
                        "open": 1660.0,
                        "high": 1680.0,
                        "low": 1655.0,
                        "close": 1675.0,
                        "volume": 1000,
                    },
                    {
                        "datetime": "2026-01-03 00:00:00",
                        "open": 1675.0,
                        "high": 1690.0,
                        "low": 1670.0,
                        "close": 1688.0,
                        "volume": 1200,
                    },
                ]
            )

    fake_quotes_module = ModuleType("mootdx.quotes")
    setattr(fake_quotes_module, "Quotes", SimpleNamespace(factory=lambda market, **kw: FakeQuotesClient()))
    monkeypatch.setitem(sys.modules, "mootdx.quotes", fake_quotes_module)

    provider = QuoteProvider()
    candles = await provider.get_kline("600519", count=2)

    assert candles == [
        {
            "time": "2026-01-02",
            "open": 1660.0,
            "high": 1680.0,
            "low": 1655.0,
            "close": 1675.0,
            "volume": 1000.0,
        },
        {
            "time": "2026-01-03",
            "open": 1675.0,
            "high": 1690.0,
            "low": 1670.0,
            "close": 1688.0,
            "volume": 1200.0,
        },
    ]


def test_get_exchange() -> None:
    assert get_exchange("600519") == "sh"
    assert get_exchange("688001") == "sh"
    assert get_exchange("000001") == "sz"
    assert get_exchange("300750") == "sz"
