from __future__ import annotations

from pydantic import BaseModel


class PostResponse(BaseModel):
    source: str
    title: str
    content: str
    author: str
    url: str
    stock_codes: list[str]
    published_at: str
    id: int


class SearchResponse(BaseModel):
    results: list[PostResponse]
    total: int


class RecentPostsResponse(BaseModel):
    posts: list[PostResponse]


class StockDetailResponse(BaseModel):
    code: str
    name: str
    posts: list[PostResponse]


class KeywordCreate(BaseModel):
    keyword: str


class KeywordResponse(BaseModel):
    id: int
    keyword: str
    created_at: str


class HealthResponse(BaseModel):
    status: str
    sources: dict[str, dict[str, str | int | None]]
    uptime: int
