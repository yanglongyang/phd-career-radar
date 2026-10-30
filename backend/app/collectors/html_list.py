"""Bounded, same-origin pagination for traditional public recruitment lists."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from app.collectors.base import JobCollector, RawJob
from app.collectors.config import SourceConfig, extract_date_text, title_require_filter
from app.collectors.html_detail import (
    outside_history_window,
    public_link,
    read_article,
    reconcile_article_metadata,
)
from app.collectors.http import SafeFetcher


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(url)
    return parsed.scheme.lower(), (parsed.hostname or "").lower(), parsed.port


class HtmlListCollector(JobCollector):
    type_name = "html_list"

    def __init__(self, source: SourceConfig):
        self.source = source
        self.warnings: list[str] = []
        self.prefiltered_count = 0
        self.recency_prefiltered_count = 0
        self._fetcher = SafeFetcher(
            user_agent=source.request.user_agent, max_bytes=source.request.max_bytes
        )

    def _soup_from_body(self, body: str) -> BeautifulSoup:
        return BeautifulSoup(body, "html.parser")

    def _select_text(self, node, selector: str) -> str | None:
        target = node.select_one(selector) if selector else None
        return target.get_text(" ", strip=True) or None if target is not None else None

    def _select_attr(self, node, selector: str, attr: str) -> str | None:
        target = node.select_one(selector) if selector else None
        value = target.get(attr) if target is not None else None
        return value if isinstance(value, str) and value else None

    def _extract_date_text(self, node, selectors: dict) -> str | None:
        date_selector = selectors.get("date") or ""
        date_attr = selectors.get("date_attr") or ""
        raw = None
        if date_selector:
            target = node.select_one(date_selector)
            if target is not None:
                raw = target.get(date_attr) if date_attr else target.get_text(strip=True)
        return extract_date_text(raw or node.get_text(" ", strip=True))

    def _next_page(self, soup: BeautifulSoup, url: str, body: str, page_index: int) -> str | None:
        config = self.source.pagination
        selector = config.get("next_selector")
        anchor = soup.select_one(selector) if selector else None
        if anchor is None:
            labels = config.get("next_text", ["下一页", "下页", "next", "next page"])
            labels = [labels] if isinstance(labels, str) else labels
            labels = {text.strip().lower() for text in labels}
            anchor = next((a for a in soup.select("a[href]") if a.get_text(" ", strip=True).lower() in labels), None)
        href = anchor.get("href") if anchor is not None else None
        if href and not href.strip().startswith(("#", "javascript:")):
            return public_link(url, href)
        template = config.get("url_template")
        if template:
            # TRS government sites emit pagination through document.write. Reading
            # this numeric count avoids nonexistent pages; no JavaScript executes.
            count = re.search(r"\b(?:countPage|totalPages)\s*=\s*[\"']?(\d+)", body)
            if count and page_index + 1 >= int(count.group(1)):
                return None
            page_number = config.get("start_page", 1) + page_index
            return public_link(url, template.replace("{page}", str(page_number)))
        return None

    def collect(self) -> list[RawJob]:
        self.warnings = []
        self.prefiltered_count = 0
        self.recency_prefiltered_count = 0
        selectors = self.source.selectors
        item_selector = selectors.get("item")
        if not item_selector:
            raise ValueError(f"[{self.source.id}] selectors.item 缺失")
        limits = dict(self.source.pagination)
        if self.source.scope == "history":
            limits.update(self.source.history)
        max_pages = limits.get("max_pages", 1)
        max_items = limits.get("max_items", 100)
        fetch_detail = self.source.detail.get("fetch_detail", False)
        results: list[RawJob] = []
        pages_seen: set[str] = set()
        jobs_seen: set[str] = set()
        current = self.source.url
        origin = None

        for page_index in range(max_pages):
            if current in pages_seen:
                self.warnings.append("分页出现重复链接，已停止翻页")
                break
            pages_seen.add(current)
            try:
                final_url, _, body = self._fetcher.fetch(
                    current, timeout=self.source.request.timeout_seconds, content_types=("html", "text")
                )
            except Exception as exc:
                if page_index == 0:
                    raise
                self.warnings.append(f"第 {page_index + 1} 页抓取失败：{str(exc)[:200]}")
                break
            if origin is None:
                origin = _origin(final_url)
            elif _origin(final_url) != origin:
                self.warnings.append("分页被重定向到其他站点，已停止翻页")
                break
            if final_url != current and final_url in pages_seen:
                self.warnings.append("分页重定向回已采集页面，已停止翻页")
                break
            pages_seen.add(final_url)
            soup = self._soup_from_body(body)
            nodes = soup.select(item_selector)
            if not nodes:
                self.warnings.append(f"第 {page_index + 1} 页列表选择器未匹配，需核查页面结构或访问状态")
                break
            before = len(jobs_seen)
            for node in nodes:
                url = public_link(final_url, self._select_attr(node, selectors.get("link") or "a", "href"))
                title = self._select_text(node, selectors.get("title") or "a")
                if not url or url in jobs_seen or not title or not title_require_filter(
                    title, selectors.get("title_require_words")
                ):
                    continue
                date_raw = self._extract_date_text(node, selectors)
                if self.source.require_date and not date_raw:
                    continue
                jobs_seen.add(url)
                excluded_words = list(self.source.filters.get("exclude_title_keywords") or [])
                if self.source.filters.get("exclude_scope", "title") != "content":
                    excluded_words += self.source.filters.get("exclude_keywords") or []
                if any(str(word).lower() in title.lower() for word in excluded_words):
                    # Preserve audit counts while spending the detail budget on
                    # announcements, rather than on result/appointment notices.
                    self.prefiltered_count += 1
                    continue
                if outside_history_window(self.source, title, date_raw):
                    self.recency_prefiltered_count += 1
                    continue
                if len(results) >= max_items:
                    self.warnings.append(f"达到 {max_items} 条采集上限；还有公告未抓取")
                    return results
                payload: dict = {
                    "list_item": str(node)[:2000], "list_url": final_url,
                    "detail_status": "not_requested", "attachments": [], "images": [],
                }
                description = None
                if fetch_detail:
                    try:
                        article = read_article(self._fetcher, self.source, url)
                        description = article["description"]
                        payload.update(article["payload"])
                        title, date_raw = reconcile_article_metadata(
                            title, date_raw, article, payload, self.warnings, "list"
                        )
                        if payload["detail_status"] != "complete":
                            self.warnings.append(f"{url}: {payload['detail_error']}")
                    except Exception as exc:
                        payload.update({"detail_status": "failed", "detail_error": str(exc)[:300]})
                        self.warnings.append(f"详情抓取失败 {url}: {str(exc)[:150]}")
                if outside_history_window(self.source, title, date_raw):
                    self.recency_prefiltered_count += 1
                    continue
                results.append(RawJob(
                    source_id=self.source.id, source_name=self.source.name, title=title,
                    source_url=url, published_at_raw=date_raw, description_raw=description,
                    organization_hint=self.source.organization,
                    location_hint=self.source.location or self.source.province, raw_payload=payload,
                ))
            next_url = self._next_page(soup, final_url, body, page_index)
            if not next_url:
                break
            if _origin(next_url) != origin:
                self.warnings.append("下一页指向其他站点，已停止翻页")
                break
            if next_url in pages_seen:
                self.warnings.append("分页出现重复链接，已停止翻页")
                break
            if page_index + 1 >= max_pages:
                if self.source.scope == "history":
                    self.warnings.append(f"达到 {max_pages} 页上限；仍有更早公告未遍历")
                break
            if len(jobs_seen) == before and page_index > 0:
                if any(public_link(final_url, self._select_attr(n, selectors.get("link") or "a", "href"))
                       in jobs_seen for n in nodes):
                    self.warnings.append("分页未返回新的公告链接，已停止翻页")
                    break
            current = next_url
        if not results and not self.warnings and not self.prefiltered_count and not self.recency_prefiltered_count:
            self.warnings.append("列表可读取，但没有匹配的招聘条目；请核查筛选条件和来源结构")
        return results
