from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportAny=false

import json
from pathlib import Path

import httpx
import pytest

from stock_hub.scrapers.cninfo import CNInfoScraper
from stock_hub.storage.models import Post


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "cninfo_response.json"


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_parse_cninfo_announcements() -> None:
    scraper = CNInfoScraper()
    payload = load_fixture()

    posts = scraper.parse_announcements(payload)

    assert len(posts) == 2
    assert all(isinstance(post, Post) for post in posts)
    assert posts[0].source == "cninfo"
    assert posts[0].title == "贵州茅台(600519): 2024年年度报告"
    assert posts[0].content == "贵州茅台酒股份有限公司2024年年度报告..."
    assert posts[0].url == "http://static.cninfo.com.cn/finalpage/2024-03-28/1234567890.PDF"
    assert posts[0].stock_codes == ["600519"]
    assert posts[0].published_at == "2024-03-28 00:00:00"


def test_stock_code_extraction() -> None:
    scraper = CNInfoScraper()

    assert scraper.extract_stock_codes("贵州茅台(600519): 2024年年度报告") == ["600519"]


class MockHttpClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload: dict[str, object] = payload
        self.requests: list[dict[str, object]] = []

    async def post(self, url: str, **kwargs: object) -> httpx.Response:
        self.requests.append({"url": url, **kwargs})
        request = httpx.Request("POST", url)
        return httpx.Response(status_code=200, json=self.payload, request=request)


@pytest.mark.asyncio
async def test_fetch_latest_with_mock() -> None:
    payload = load_fixture()
    client = MockHttpClient(payload)
    scraper = CNInfoScraper(client=client)  # type: ignore[arg-type]

    posts = await scraper.fetch_latest(limit=2)

    assert len(posts) == 2
    request = client.requests[0]
    assert request["url"] == "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    assert request["headers"] == {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "http://www.cninfo.com.cn/",
    }
    assert request["data"] == {
        "tabName": "fulltext",
        "pageSize": 2,
        "pageNum": 1,
        "isHLtitle": "true",
    }


@pytest.mark.asyncio
async def test_search_with_keyword() -> None:
    payload = load_fixture()
    client = MockHttpClient(payload)
    scraper = CNInfoScraper(client=client)  # type: ignore[arg-type]

    posts = await scraper.search("半导体", limit=5)

    assert len(posts) == 2
    assert posts[1].title == "中芯国际(688981): 关于半导体行业发展公告"
    request = client.requests[0]
    assert request["url"] == "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    data = request["data"]
    assert isinstance(data, dict)
    assert data["searchkey"] == "半导体"
    assert data["pageSize"] == 5


def test_parse_skips_non_dict_announcements() -> None:
    scraper = CNInfoScraper()

    posts = scraper.parse_announcements({"announcements": ["bad", {"announcementTitle": "测试(000001)"}]})

    assert len(posts) == 1
    assert posts[0].stock_codes == ["000001"]
