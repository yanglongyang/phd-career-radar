"""Public announcement pages and conservative HTML detail extraction.

Linked documents and images are recorded as unparsed evidence. This collector
does not claim to read a PDF, spreadsheet or image merely because it found a URL.
"""

from __future__ import annotations

import re
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag

from app.collectors.base import JobCollector, RawJob
from app.collectors.config import SourceConfig, extract_date_text
from app.collectors.http import SafeFetcher

DEFAULT_CONTENT_SELECTORS = (
    ".v_news_content", "#vsb_content_2", "#vsb_content", ".TRS_Editor", ".trs_editor_view", ".TRS_UEDITOR", "#zoom",
    "article", ".article-content", ".news_content", ".detail-content", ".content-detail", ".wznr",
)
ATTACHMENT_EXTENSIONS = re.compile(r"\.(?:pdf|docx?|xlsx?|pptx?|zip|rar|7z|csv|txt)(?:$|[?#])", re.I)
BLOCK_TAGS = {
    "p", "div", "section", "article", "header", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "ul", "ol", "blockquote", "table", "dl", "dt", "dd", "address", "figure", "figcaption",
}
TABLE_HEADER_WORDS = (
    "类别", "分类", "档次", "层次", "类型", "待遇", "项目", "人才", "学科", "专业", "学位",
    "薪酬", "工资", "年薪", "安家", "经费", "补贴", "补助", "津贴", "资助", "住房", "科研",
)


def outside_history_window(source: SourceConfig, title: str | None, published: str | None) -> bool:
    """Use the same year evidence as persistence; an unknown year stays eligible."""
    if source.scope != "history":
        return False
    # Local import keeps the collectors' module initialization independent of the
    # service layer while avoiding two competing announcement-year rules.
    from app.services.announcement_reference import announcement_year, current_year

    year, _ = announcement_year(title, published)
    now = current_year()
    return year is not None and not now - source.history.get("years", 3) <= year < now


def _plain_text(node: Tag) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def _table_lines(table: Tag) -> list[str]:
    """Keep cells together and carry explicit column headings into data rows.

    Only simple one-row headings are mapped to cells. For merged or multilevel
    headings we retain the original cell order and repeat the heading context;
    we do not guess which amount belongs to which merged column.
    """
    rows = [row for row in table.find_all("tr") if row.find_parent("table") is table]
    rendered: list[str] = []
    header_rows: list[list[str]] = []
    simple = True
    data_started = False
    caption = table.find("caption", recursive=False)
    if caption and _plain_text(caption):
        rendered.append(_plain_text(caption))
    for row in rows:
        cells = row.find_all(["th", "td"], recursive=False)
        values = [_plain_text(cell) for cell in cells]
        if not cells or not any(values):
            continue
        merged = any(str(cell.get(attr, "1")) != "1" for cell in cells for attr in ("colspan", "rowspan"))
        all_heading = all(cell.name == "th" for cell in cells)
        # Older university CMS tables often use td for their headings. Recognize
        # explicit field words, but never treat a numeric salary row as headings.
        has_header_words = any(word in value for value in values for word in TABLE_HEADER_WORDS)
        has_amount = any(re.search(r"\d[\d.,～~—–\-]*\s*(?:万|元)", value) for value in values)
        heading = not data_started and (all_heading or has_header_words and not has_amount)
        if heading:
            header_rows.append(values)
            simple = simple and not merged
            rendered.append(" | ".join(values))
            continue
        data_started = True
        labels = header_rows[0] if len(header_rows) == 1 else []
        if simple and not merged and labels and len(labels) == len(values):
            rendered.append(" | ".join(
                f"{label}：{value}" if label else value for label, value in zip(labels, values, strict=True)
            ))
        elif header_rows:
            context = " / ".join(" | ".join(values) for values in header_rows)
            rendered.append(f"表格列（{context}）：" + " | ".join(values))
        else:
            rendered.append(" | ".join(values))
    return rendered or [_plain_text(table)]


def article_text(content: Tag) -> str:
    """Emit paragraphs once, keeping inline spans and table cells on their row."""
    def render(node: Tag) -> list[str]:
        if node.name == "table":
            return _table_lines(node)
        lines: list[str] = []
        inline: list[str] = []

        def flush() -> None:
            value = re.sub(r"\s+", " ", "".join(inline)).strip()
            if value:
                lines.append(value)
            inline.clear()

        for child in node.children:
            if isinstance(child, NavigableString):
                inline.append(str(child))
            elif isinstance(child, Tag):
                if child.name == "br":
                    flush()
                elif child.name in BLOCK_TAGS:
                    flush()
                    lines.extend(render(child))
                else:
                    # Inline markup does not imply a paragraph boundary. The
                    # subtree is consumed here and is never visited a second time.
                    inline.append(child.get_text("", strip=False))
        flush()
        return lines

    return "\n".join(render(content))


def public_link(base: str, href: str | None) -> str | None:
    """Resolve HTML links; fetches still go through SafeFetcher's public-IP check."""
    if not href or not isinstance(href, str) or href.strip().startswith("#"):
        return None
    url = urldefrag(urljoin(base, href.strip()))[0]
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        return None
    return url


def _article_title(soup: BeautifulSoup, source: SourceConfig) -> tuple[str | None, str]:
    selector = source.detail.get("title_selector")
    node = soup.select_one(selector) if selector else None
    if node:
        return node.get_text(" ", strip=True) or None, "configured_selector"
    meta = soup.find("meta", attrs={"name": "ArticleTitle"}) or soup.find(
        "meta", attrs={"property": "og:title"}
    )
    if meta and meta.get("content"):
        return str(meta["content"]).strip(), "article_meta"
    node = soup.select_one("h1")
    if node:
        return node.get_text(" ", strip=True) or None, "h1"
    return (soup.title.get_text(" ", strip=True), "document_title") if soup.title else (None, "missing")


def reconcile_article_metadata(
    title: str | None, published: str | None, article: dict, payload: dict,
    warnings: list[str], origin: str,
) -> tuple[str | None, str | None]:
    """A repurposed URL must not attach a new year's benefits to an old seed."""
    from app.services.announcement_reference import announcement_year

    article_title = article.get("title")
    trusted = article.get("title_source") in {"configured_selector", "article_meta", "h1"}
    original_year, _ = announcement_year(title, published)
    body_year, _ = announcement_year(article_title, None)
    if trusted and body_year is not None and body_year != original_year:
        payload[f"{origin}_title"] = title
        payload[f"{origin}_published_at"] = published
        if original_year is not None:
            conflict = f"{origin} 标注 {original_year} 年，正文标题为 {body_year} 年；已采用正文标题及日期"
            payload["metadata_conflict"] = conflict
            warnings.append(conflict)
        return article_title, article.get("published_at")
    return title or article_title, published or article.get("published_at")


def _publication_date(soup: BeautifulSoup, source: SourceConfig) -> str | None:
    selector = source.detail.get("date_selector")
    if selector:
        node = soup.select_one(selector)
        if node:
            found = extract_date_text(node.get_text(" ", strip=True))
            if found:
                return found
    # These are publication-specific fields; don't mistake an application deadline
    # found in the body or a footer's current date for the announcement date.
    for attrs in (
        {"name": "PubDate"}, {"name": "pubdate"}, {"name": "publishdate"},
        {"name": "Date"}, {"property": "article:published_time"}, {"itemprop": "datePublished"},
    ):
        node = soup.find("meta", attrs=attrs)
        found = extract_date_text(str(node.get("content", ""))) if node else None
        if found:
            return found
    text = soup.get_text(" ", strip=True)
    found = re.search(
        r"(?:发布时间|发布日期|发表时间)\s*[:：]?\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?)", text
    )
    return found.group(1) if found else None


def read_article(fetcher: SafeFetcher, source: SourceConfig, url: str) -> dict:
    final_url, _, body = fetcher.fetch(
        url, timeout=source.request.timeout_seconds, content_types=("html", "text")
    )
    soup = BeautifulSoup(body, "html.parser")
    title, title_source = _article_title(soup, source)
    published = _publication_date(soup, source)
    selector = source.detail.get("content_selector")
    if selector:
        content = soup.select_one(selector)
    else:
        content = next((node for css in DEFAULT_CONTENT_SELECTORS if (node := soup.select_one(css))), None)
    payload: dict = {
        "detail_url": final_url, "detail_status": "missing", "attachments": [], "images": [],
        "article_title": title, "article_title_source": title_source,
    }
    # Some employer portals put a bare amount in a dedicated salary element,
    # outside the paragraphs. Only a verified source-specific selector may give
    # that amount salary semantics; never scan the page for arbitrary numbers.
    salary_selector = source.detail.get("salary_selector")
    salary_node = soup.select_one(salary_selector) if salary_selector else None
    salary_text = _plain_text(salary_node) if salary_node else None
    if salary_text:
        payload["salary_text"] = salary_text
    if content is None:
        payload["detail_error"] = "正文选择器未匹配；请打开原网页核对或更新来源配置"
        return {
            "title": title, "title_source": title_source, "published_at": published,
            "description": None, "payload": payload,
        }

    for node in content.select("script, style, noscript, nav, footer"):
        node.decompose()
    attachments = []
    images = []
    seen: set[str] = set()
    # VSB universities place attachment <ul> next to the body, inside the same
    # article form. Include that form, never the site's unrelated navigation.
    attachment_root = content.find_parent("form", attrs={"name": "_newscontent_fromname"}) or content
    for anchor in attachment_root.select("a[href]"):
        link = public_link(final_url, anchor.get("href"))
        label = anchor.get_text(" ", strip=True)
        if link and link not in seen and (
            ATTACHMENT_EXTENSIONS.search(link) or ATTACHMENT_EXTENSIONS.search(label)
            or "附件" in label or "/download" in urlsplit(link).path.lower()
        ):
            attachments.append({"url": link, "title": label or "附件", "parsed": False})
            seen.add(link)
    for image in content.select("img"):
        link = public_link(final_url, image.get("src") or image.get("data-src"))
        if link and link not in seen:
            images.append({"url": link, "alt": str(image.get("alt", "")), "parsed": False})
            seen.add(link)
    text = article_text(content)
    if salary_text:
        text = f"薪资（原文）：{salary_text}\n{text}".strip()
    payload.update({
        "attachments": attachments[:100], "images": images[:100],
        "has_unparsed_attachments": bool(attachments), "has_unparsed_images": bool(images),
        "detail_status": "complete" if text else "missing",
    })
    if not text:
        payload["detail_error"] = "正文没有可提取文字；图片与附件尚未解析"
    return {
        "title": title, "title_source": title_source, "published_at": published,
        "description": text or None, "payload": payload,
    }


class HtmlDetailCollector(JobCollector):
    """Fetch verified announcement seeds when a list is unavailable or incomplete."""

    type_name = "html_detail"

    def __init__(self, source: SourceConfig):
        self.source = source
        self.warnings: list[str] = []
        self.recency_prefiltered_count = 0
        self._fetcher = SafeFetcher(source.request.user_agent, source.request.max_bytes)

    def collect(self) -> list[RawJob]:
        self.warnings = []
        self.recency_prefiltered_count = 0
        if self.source.history.get("only") and self.source.scope != "history":
            return []
        results: list[RawJob] = []
        seen: set[str] = set()
        seeds = self.source.raw.get("seeds") or [{"url": self.source.url}]
        limits = self.source.history if self.source.scope == "history" else self.source.pagination
        maximum = limits.get("max_items", 200)
        for seed in seeds:
            url = public_link(self.source.url, seed["url"])
            if not url or url in seen:
                continue
            seen.add(url)
            title = seed.get("title")
            published = seed.get("published_at")
            if outside_history_window(self.source, title, published):
                self.recency_prefiltered_count += 1
                continue
            if len(results) >= maximum:
                self.warnings.append(f"达到 {maximum} 条采集上限，部分公告种子未抓取")
                break
            description = None
            payload: dict = {"seed_url": url}
            try:
                article = read_article(self._fetcher, self.source, url)
                description = article["description"]
                payload.update(article["payload"])
                title, published = reconcile_article_metadata(
                    title, published, article, payload, self.warnings, "seed"
                )
                if payload["detail_status"] != "complete":
                    self.warnings.append(f"{url}: {payload['detail_error']}")
            except Exception as exc:  # one unavailable seed must not erase other announcements
                payload.update({"detail_status": "failed", "detail_error": str(exc)[:300]})
                self.warnings.append(f"详情抓取失败 {url}: {str(exc)[:150]}")
            if outside_history_window(self.source, title, published):
                self.recency_prefiltered_count += 1
                continue
            results.append(RawJob(
                source_id=self.source.id, source_name=self.source.name,
                title=title, source_url=url, published_at_raw=published,
                description_raw=description,
                organization_hint=seed.get("organization") or self.source.organization,
                sector_hint=seed.get("sector"), location_hint=self.source.location or self.source.province,
                raw_payload=payload,
            ))
        return results
