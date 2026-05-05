from __future__ import annotations

from pathlib import Path
import tomllib

_CONFIG_CACHE: dict | None = None


def _candidate_paths() -> list[Path]:
    return [Path.cwd() / "config.toml", Path(r"E:\re0\stock-hub") / "config.toml"]


def _load_toml(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def get_config() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    for path in _candidate_paths():
        if path.is_file():
            _CONFIG_CACHE = _load_toml(path)
            return _CONFIG_CACHE
    _CONFIG_CACHE = {}
    return _CONFIG_CACHE
