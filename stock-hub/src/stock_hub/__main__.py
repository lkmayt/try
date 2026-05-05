"""Stock Hub entry point: python -m stock_hub"""

# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportAny=false, reportExplicitAny=false

import logging
import uvicorn

from typing import Any

from stock_hub.config import get_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    config: dict[str, Any] = get_config()
    server = config.get("server", {})
    host = server.get("host", "127.0.0.1") if isinstance(server, dict) else "127.0.0.1"
    port = server.get("port", 8000) if isinstance(server, dict) else 8000
    uvicorn.run(
        "stock_hub.api.app:app",
        host=str(host),
        port=int(port),
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
