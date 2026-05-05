from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Post:
    source: str
    title: str
    content: str = ""
    author: str = ""
    url: str = ""
    stock_codes: list[str] = field(default_factory=list)
    published_at: str = ""
    scraped_at: str = ""
    id: int | None = None
