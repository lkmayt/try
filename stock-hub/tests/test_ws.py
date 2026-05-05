from __future__ import annotations

import pytest
from starlette.websockets import WebSocketDisconnect

from stock_hub.api.ws import ConnectionManager


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted: bool = False
        self.messages: list[dict[str, object]] = []
        self.raise_on_send: bool = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict[str, object]) -> None:
        if self.raise_on_send:
            raise WebSocketDisconnect()
        self.messages.append(data)


@pytest.mark.asyncio
async def test_connection_manager_lifecycle() -> None:
    manager = ConnectionManager()
    websocket = FakeWebSocket()

    await manager.connect(websocket, "600519")

    assert websocket.accepted is True
    assert websocket in manager._connections["600519"]

    await manager.disconnect(websocket)

    assert "600519" not in manager._connections
    assert websocket not in manager._subscriptions


@pytest.mark.asyncio
async def test_broadcast_to_subscribers() -> None:
    manager = ConnectionManager()
    websocket_a = FakeWebSocket()
    websocket_b = FakeWebSocket()

    await manager.connect(websocket_a, "600519")
    await manager.connect(websocket_b, "600519")
    await manager.broadcast("600519", {"code": "600519", "price": 1688.0})

    assert websocket_a.messages == [{"code": "600519", "price": 1688.0}]
    assert websocket_b.messages == [{"code": "600519", "price": 1688.0}]

    await manager.disconnect(websocket_a)
    await manager.disconnect(websocket_b)


@pytest.mark.asyncio
async def test_no_cross_broadcast() -> None:
    manager = ConnectionManager()
    websocket_a = FakeWebSocket()
    websocket_b = FakeWebSocket()

    await manager.connect(websocket_a, "600519")
    await manager.connect(websocket_b, "000001")
    await manager.broadcast("600519", {"code": "600519", "price": 1688.0})

    assert websocket_a.messages == [{"code": "600519", "price": 1688.0}]
    assert websocket_b.messages == []

    await manager.disconnect(websocket_a)
    await manager.disconnect(websocket_b)
