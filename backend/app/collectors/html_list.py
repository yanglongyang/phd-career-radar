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
from app.collectors.config import SourceConfig
from app.collectors.http import SafeFetcher


class HtmlListCollector(JobCollector):
    type_name = "html_list"

    def __init__(self, source: SourceConfig):
        self.source = source
        self._fetcher = SafeFetcher(
            user_agent=source.request.user_agent, max_bytes=source.request.max_bytes
        )

    def _soup(self, url: str) -> BeautifulSoup:
        _, _, body = self._fetcher.fetch(
            url,
            timeout=self.source.request.timeout_seconds,
            content_types=("html", "text"),
        )
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

    def collect(self) -> list[RawJob]:
        selectors = self.source.selectors
        item_selector = selectors.get("item")
        if not item_selector:
            raise ValueError(f"[{self.source.id}] selectors.item 缺失")

        final_url, _, _ = self._fetcher.fetch(
            self.source.url,
            timeout=self.source.request.timeout_seconds,
            content_types=("html", "text"),
        )
        soup = self._soup(self.source.url)
        items = soup.select(item_selector)
        if not items:
            return []

        detail_config = self.source.detail or {}
        fetch_detail = bool(detail_config.get("fetch_detail", False))
        content_selector = detail_config.get("content_selector", "")

        results: list[RawJob] = []
        for node in items:
            href = self._select_attr(node, selectors.get("link") or "a", "href")
            if not href:
                continue
            url = urljoin(final_url, href)
            title = self._select_text(node, selectors.get("title") or "a")
            date_raw = self._select_text(node, selectors.get("date") or "")

            description = None
            if fetch_detail:
                try:
                    detail_soup = self._soup(url)
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
