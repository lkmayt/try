from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

from stock_hub.scrapers.base import BaseScraper
from stock_hub.scrapers.http_client import HttpClient
from stock_hub.storage.models import Post


logger = logging.getLogger(__name__)


class SZSEInteractiveScraper(BaseScraper):
    source_name = "szse"

    def __init__(self, client: HttpClient | None = None, http_client: HttpClient | None = None, use_akshare: bool = True) -> None:
        self.client = http_client or client or HttpClient()
        self._use_akshare = use_akshare

    async def fetch_latest(self, limit: int = 30) -> list[Post]:
        # SZSE API is per-stock only, no general feed exists.
        # Background fetch would require an arbitrary stock list.
        # Instead, rely on search() for real-time, on-demand fetching.
        return []

    async def search(self, keyword: str, limit: int = 30) -> list[Post]:
        stock_code = self._extract_stock_code(keyword)
        if not stock_code:
            return []

        if self._use_akshare:
            posts = await self._try_akshare(stock_code=stock_code, limit=limit)
            if posts:
                return posts[:limit]
        return await self._fetch_via_http(limit=limit, keyword=stock_code)

    async def _try_akshare(self, stock_code: str = "000001", limit: int = 30) -> list[Post]:
        import asyncio
        try:
            import akshare as ak  # type: ignore
            questions = await asyncio.to_thread(ak.stock_irm_cninfo, symbol=stock_code)
        except Exception as exc:
            logger.warning("AKShare SZSE questions failed: %s", exc)
            return []

        if questions is None or getattr(questions, "empty", True):
            return []

        # Fetch answers separately (may fail if API changed)
        answer_map: dict[str, Any] = {}
        try:
            answers = await asyncio.to_thread(ak.stock_irm_ans_cninfo, symbol=stock_code)
            if answers is not None and not getattr(answers, "empty", True):
                for _, row in answers.iterrows():
                    key = self._clean_text(str(row.get("问题", row.get("question", ""))))
                    if key:
                        answer_map[key] = row
        except Exception as exc:
            logger.info("AKShare SZSE answers unavailable: %s", exc)

        posts: list[Post] = []
        for _, row in questions.iterrows():
            # akshare DataFrame uses Chinese column names
            question = self._clean_text(str(
                row.get("问题", row.get("question", row.get("title", "")))
            ))
            answer_row = answer_map.get(question)
            answer = ""
            if answer_row is not None:
                answer = self._clean_text(str(
                    answer_row.get("回答内容", answer_row.get("answer", answer_row.get("content", "")))
                ))
            posts.append(
                Post(
                    source=self.source_name,
                    title=self._summarize_question(question),
                    content=self._compose_content(question, answer),
                    author=self._clean_text(str(
                        row.get("公司简称", row.get("company_name", row.get("提问者", "")))
                    )),
                    url=self._build_question_url(row),
                    published_at=self._normalize_date(str(
                        row.get("提问时间", row.get("date", row.get("publish_time", "")))
                    )),
                    scraped_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            if len(posts) >= limit:
                break
        return posts

    async def _fetch_via_http(self, limit: int = 30, keyword: str | None = None) -> list[Post]:
        url = self._build_url(keyword=keyword)
        response = await self.client.get(url)
        response.raise_for_status()
        return self._parse_html(response.text, limit=limit)

    def _build_url(self, keyword: str | None = None) -> str:
        params = ["condition.type=2", "condition.stocktype=S"]
        if keyword:
            params.append(f"condition.stockcode={keyword}")
        else:
            params.append("condition.stockcode=000001")
        return "http://irm.cninfo.com.cn/ircs/interaction/lastQuestionforSzseSsgs.do?" + "&".join(params)

    def _parse_html(self, html: str, limit: int = 30) -> list[Post]:
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".question-item, li, .item")
        posts: list[Post] = []
        for item in items:
            post = self._parse_item(item)
            if post is None:
                continue
            posts.append(post)
            if len(posts) >= limit:
                break
        return posts

    def _parse_item(self, item: Any) -> Post | None:
        question = self._extract_text(item, ["question", "title", "q"]) or self._clean_text(item.get_text(" ", strip=True))
        if not question:
            return None
        answer = self._extract_text(item, ["answer", "reply", "a"])
        company = self._extract_text(item, ["company", "company_name", "org"])
        published_at = self._normalize_date(self._extract_text(item, ["date", "time", "publish_time"]))
        return Post(
            source=self.source_name,
            title=self._summarize_question(question),
            content=self._compose_content(question, answer),
            author=company,
            published_at=published_at,
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )

    def _extract_text(self, item: Any, names: list[str]) -> str:
        for name in names:
            node = item.select_one(f".{name}, [data-field='{name}']") if hasattr(item, "select_one") else None
            if node:
                return self._clean_text(node.get_text(" ", strip=True))
        return ""

    def _extract_stock_code(self, keyword: str) -> str:
        match = re.search(r"\b\d{6}\b", keyword)
        return match.group(0) if match else ""

    def _build_question_url(self, row: Any) -> str:
        """Generate a unique URL from the question ID."""
        qid = str(row.get("问题ID", row.get("问题编号", ""))).strip()
        if qid:
            return f"https://irm.cninfo.com.cn/ircs/question/detail?questionId={qid}"
        return f"https://irm.cninfo.com.cn/ircs/company/companyDetail?stockcode={row.get('股票代码', '000001')}"

    def _summarize_question(self, question: str) -> str:
        return question[:80]

    def _compose_content(self, question: str, answer: str) -> str:
        return f"Question: {question}\nAnswer: {answer}".strip()

    def _normalize_date(self, value: str) -> str:
        value = self._clean_text(value)
        if not value:
            return ""
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(value[:19], fmt).date().isoformat()
            except ValueError:
                continue
        return value

    def _clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()
