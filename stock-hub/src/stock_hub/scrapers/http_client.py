from __future__ import annotations

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportAny=false

import asyncio
import logging

import httpx


logger = logging.getLogger(__name__)


class HttpClient:
    """Thin async httpx client wrapper with retry support."""

    def __init__(self, timeout: float = 15.0, max_retries: int = 3) -> None:
        self.timeout: float = timeout
        self.max_retries: int = max_retries
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                trust_env=False,  # 不走系统代理，国内金融站点直连
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36"
                    )
                },
            )
        return self._client

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        client = await self._get_client()
        last_exc: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await client.request(method, url, **kwargs)
                if response.status_code >= 500 and attempt < self.max_retries - 1:
                    wait = 2**attempt
                    logger.warning("Server error %s, retry in %ss", response.status_code, wait)
                    await asyncio.sleep(wait)
                    continue
                return response
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    wait = 2**attempt
                    logger.warning("Connection error, retry in %ss: %s", wait, exc)
                    await asyncio.sleep(wait)
                    continue
                break

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("HTTP request failed without a response or captured exception")

    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
