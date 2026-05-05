"""Persistent sync state — tracks when each scraper last successfully fetched."""

from __future__ import annotations

import json
from datetime import datetime, UTC, timezone
from pathlib import Path
from typing import Any

SYNC_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "last_sync.json"


def _ensure_dir() -> None:
    SYNC_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_sync_state() -> dict[str, str]:
    """Return {source_name: iso_timestamp} or empty dict if no state exists."""
    try:
        text = SYNC_FILE.read_text(encoding="utf-8-sig")  # -sig removes BOM
        data = json.loads(text)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        pass
    return {}


def save_sync_state(source_name: str, timestamp: str | None = None) -> None:
    """Record that a source successfully scraped. Timestamp defaults to now (UTC)."""
    state = load_sync_state()
    ts = timestamp or datetime.now(UTC).isoformat()
    state[source_name] = ts
    _ensure_dir()
    SYNC_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def get_last_sync(source_name: str) -> str | None:
    """Get ISO timestamp of last successful sync, or None."""
    state = load_sync_state()
    return state.get(source_name)


def should_catch_up(source_name: str, interval_seconds: int = 60) -> bool:
    """Return True if the last sync was too long ago (gap > 5x interval)."""
    last = get_last_sync(source_name)
    if last is None:
        return False  # First run — no catch-up needed
    try:
        last_dt = datetime.fromisoformat(last).replace(tzinfo=UTC)
        gap = (datetime.now(UTC) - last_dt).total_seconds()
        return gap > interval_seconds * 5
    except (ValueError, TypeError):
        return False
