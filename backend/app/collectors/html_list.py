"""HtmlListCollector（V0.2）：selector 驱动的传统高校/研究院 CMS 列表页。

- selector 全部来自 sources.yaml（item/title/link/date/content）；
- 相对 URL resolve；
- detail.fetch_detail=false 时只保存列表页信息；
- 单条 detail 失败不导致整个 source 失败（跳过该条并计数）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.collectors.base import JobCollector, RawJob
from app.collectors.config import (
    SourceConfig,
    extract_date_text,
    title_require_filter,
)
from app.collectors.http import SafeFetcher


class HtmlListCollector(JobCollector):
    type_name = "html_list"

    def __init__(self, source: SourceConfig):
        self.source = source
        self._fetcher = SafeFetcher(
            user_agent=source.request.user_agent, max_bytes=source.request.max_bytes
        )

    def _soup_from_body(self, body: str) -> BeautifulSoup:
        return BeautifulSoup(body, "html.parser")

    def _select_text(self, node, selector: str) -> str | None:
        if not selector:
            return None
        target = node.select_one(selector) if selector else None
        if target is None:
            return None
        return target.get_text(strip=True) or None

    def _select_attr(self, node, selector: str, attr: str) -> str | None:
        if not selector:
            return None
        target = node.select_one(selector) if selector else None
        if target is None:
            return None
        value = target.get(attr)
        return value if value else None

    def _clean_text(self, html: str) -> str:
        text = re.sub(r"<(script|style)\b[^>]*>.*?</\1\s*>", "", html, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _extract_date_text(self, node, selectors: dict) -> str | None:
        """从列表行提取发布日期的原始文本（仅取匹配到的日期串，便于展示）。

        - date 选择器存在：取其文本，或 date_attr 指定的属性（北大日期在 title 属性里）；
        - date 选择器缺失/取不到：扫描整行文本（华科日期嵌在 li 文本末尾）。"""
        date_selector = selectors.get("date") or ""
        date_attr = selectors.get("date_attr") or ""
        raw: str | None = None
        if date_selector:
            target = node.select_one(date_selector)
            if target is not None:
                raw = target.get(date_attr) if date_attr else target.get_text(strip=True)
        if not raw:
            raw = node.get_text(strip=True)
        if not raw:
            return None
        return extract_date_text(raw)

    def collect(self) -> list[RawJob]:
        selectors = self.source.selectors
        item_selector = selectors.get("item")
        if not item_selector:
            raise ValueError(f"[{self.source.id}] selectors.item 缺失")

        # cleanup 10：一次 GET 拿回 body，直接解析（不再重复请求列表页）
        final_url, _, body = self._fetcher.fetch(
            self.source.url,
            timeout=self.source.request.timeout_seconds,
            content_types=("html", "text"),
        )
        soup = self._soup_from_body(body)
        items = soup.select(item_selector)
        if not items:
            return []

        detail_config = self.source.detail or {}
        fetch_detail = bool(detail_config.get("fetch_detail", False))
        content_selector = detail_config.get("content_selector", "")

        results: list[RawJob] = []
        require_words = selectors.get("title_require_words")
        for node in items:
            href = self._select_attr(node, selectors.get("link") or "a", "href")
            if not href:
                continue
            url = urljoin(final_url, href)
            title = self._select_text(node, selectors.get("title") or "a")
            if not title:
                continue
            # 标题特征过滤：列表页可能混入导航/新闻，标题不含招聘特征词则跳过
            if not title_require_filter(title, require_words):
                continue
            date_raw = self._extract_date_text(node, selectors)
            # V0.3.2 require_date：无日期的条目不进 Inbox（导航/专题/无日期噪声）。
            # 注意在标题过滤之后执行 —— 导航项大多已由标题过滤排除。
            if self.source.require_date and not date_raw:
                continue

            description = None
            if fetch_detail:
                try:
                    _, _, detail_body = self._fetcher.fetch(
                        url,
                        timeout=self.source.request.timeout_seconds,
                        content_types=("html", "text"),
                    )
                    detail_soup = self._soup_from_body(detail_body)
                    content_node = detail_soup.select_one(content_selector) if content_selector else None
                    description = (
                        self._clean_text(str(content_node)) if content_node is not None else None
                    )
                except Exception:
                    description = None  # 单条 detail 失败不影响整个 source

            results.append(
                RawJob(
                    source_id=self.source.id,
                    source_name=self.source.name,
                    title=title,
                    source_job_id=None,
                    source_url=url,
                    published_at_raw=date_raw,
                    description_raw=description,
                    organization_hint=self.source.organization,
                    location_hint=None,
                    raw_payload={"list_item": str(node)[:2000]},
                )
            )
        return results
