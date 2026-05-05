from __future__ import annotations

# pyright: reportAny=false, reportPrivateUsage=false, reportMissingTypeStubs=false

import asyncio
import inspect
from collections.abc import Iterator

import pytest

from stock_hub.storage.database import Database


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "asyncio: run test in an asyncio event loop")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    if "asyncio" not in pyfuncitem.keywords:
        return None

    test_function = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_function):
        return None

    funcargs = {
        name: pyfuncitem.funcargs[name]
        for name in pyfuncitem._fixtureinfo.argnames
        if name in pyfuncitem.funcargs
    }
    asyncio.run(test_function(**funcargs))
    return True


@pytest.fixture
def database() -> Iterator[Database]:
    db = Database(":memory:")
    try:
        yield db
    finally:
        db.close()
