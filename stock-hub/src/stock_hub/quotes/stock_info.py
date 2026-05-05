from __future__ import annotations


def get_exchange(code: str) -> str:
    normalized = code.strip()
    if normalized.startswith(("6", "688")):
        return "sh"
    if normalized.startswith(("0", "3")):
        return "sz"
    raise ValueError(f"Unsupported stock code: {code}")


def get_stock_name(code: str) -> str:
    return code
