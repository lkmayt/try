from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Lazy cache for stock code -> name mapping
_name_cache: dict[str, str] = {}


def get_exchange(code: str) -> str:
    normalized = code.strip()
    if normalized.startswith(("6", "688")):
        return "sh"
    if normalized.startswith(("0", "3")):
        return "sz"
    raise ValueError(f"Unsupported stock code: {code}")


def get_stock_name(code: str) -> str:
    """Resolve stock name via Eastmoney API with local cache."""
    normalized = code.strip()
    if normalized in _name_cache:
        return _name_cache[normalized]

    try:
        import httpx
        with httpx.Client(timeout=5, follow_redirects=True, trust_env=False) as client:
            r = client.get(
                "https://searchapi.eastmoney.com/api/Info/Search"
                "?appid=el1902262&type=14"
                "&and14=MultiMatch/Name,Code,PinYin/" + normalized + "/true"
                "&returnfields14=Name,Code"
                "&pageIndex14=1&pageSize14=1"
                "&isAssociation14=false"
                "&token=CCSDCZSDCXYMYZYYSYYXSMDDSMDHHDJT",
            )
        r.raise_for_status()
        data = r.json()
        items = data.get("Data", []) or []
        if items and isinstance(items[0], dict):
            name = str(items[0].get("Name", "")).strip()
            if name and name != normalized:
                _name_cache[normalized] = name
                return name
    except Exception as exc:
        logger.debug("stock name lookup failed for %s: %s", normalized, exc)

    _name_cache[normalized] = normalized
    return normalized
