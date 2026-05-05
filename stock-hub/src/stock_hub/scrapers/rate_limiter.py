from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Per-source async token bucket rate limiter."""

    def __init__(self, rate: float = 1.0, burst: int = 1) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        if burst <= 0:
            raise ValueError("burst must be positive")

        self.rate: float = rate
        self.burst: int = burst
        self._tokens: float = float(burst)
        self._last_time: float = time.monotonic()
        self._lock: asyncio.Lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_time
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_time = now

            if self._tokens < 1.0:
                wait_time = (1.0 - self._tokens) / self.rate
                await asyncio.sleep(wait_time)
                self._tokens = 0.0
                self._last_time = time.monotonic()
            else:
                self._tokens -= 1.0
