from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportAny=false, reportExplicitAny=false

import asyncio
from collections import defaultdict
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from stock_hub.quotes.provider import QuoteProvider

ws_router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._alert_connections: set[WebSocket] = set()
        self._subscriptions: dict[WebSocket, str] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._provider: QuoteProvider = QuoteProvider()
        self._lock: asyncio.Lock = asyncio.Lock()

    def set_provider(self, provider: QuoteProvider) -> None:
        self._provider = provider

    async def connect(self, websocket: WebSocket, stock_code: str) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[stock_code].add(websocket)
            self._subscriptions[websocket] = stock_code
            if stock_code not in self._tasks or self._tasks[stock_code].done():
                self._tasks[stock_code] = asyncio.create_task(self._stream_quotes(stock_code))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            stock_code = self._subscriptions.pop(websocket, None)
            if stock_code is None:
                self._alert_connections.discard(websocket)
                return
            subscribers = self._connections.get(stock_code)
            if subscribers is not None:
                subscribers.discard(websocket)
                if not subscribers:
                    _ = self._connections.pop(stock_code, None)
                    task = self._tasks.pop(stock_code, None)
                    if task is not None:
                        _ = task.cancel()

    async def connect_alerts(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._alert_connections.add(websocket)

    async def broadcast_alert(self, data: dict[str, Any]) -> None:
        subscribers = list(self._alert_connections)
        stale: list[WebSocket] = []
        for websocket in subscribers:
            try:
                await websocket.send_json(data)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            await self.disconnect(websocket)

    async def broadcast(self, stock_code: str, data: dict[str, Any]) -> None:
        subscribers = list(self._connections.get(stock_code, set()))
        stale: list[WebSocket] = []
        for websocket in subscribers:
            try:
                await websocket.send_json(data)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            await self.disconnect(websocket)

    async def _stream_quotes(self, stock_code: str) -> None:
        try:
            while self._connections.get(stock_code):
                quote = await self._provider.get_realtime_quote(stock_code)
                await self.broadcast(stock_code, asdict(quote))
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            raise
        except Exception:
            return


manager = ConnectionManager()


@ws_router.websocket("/ws/quotes/{code}")
async def quotes_websocket(websocket: WebSocket, code: str) -> None:
    await manager.connect(websocket, code)
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


@ws_router.websocket("/ws/alerts")
async def alerts_websocket(websocket: WebSocket) -> None:
    await manager.connect_alerts(websocket)
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
