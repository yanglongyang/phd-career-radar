"""公开网页正文获取（Phase 3 方法 3：URL 导入）。

原则：只做最简单的公开网页下载与正文粗提取，不编写任何反爬对抗。
失败一律抛 PageFetchError，由 API 层转成明确提示"请粘贴公告全文"。
"""

from __future__ import annotations

import re

import httpx

USER_AGENT = "Mozilla/5.0 (compatible; PhDCareerRadar/0.1; personal research tool)"
MIN_TEXT_LENGTH = 50

_SCRIPT_STYLE = re.compile(
    r"<(script|style|noscript|template)\b[^>]*>.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_COMMENTS = re.compile(r"<!--.*?-->", re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")
_BLOCK_END = re.compile(r"</(p|div|li|tr|h[1-6]|section|article|table)>", re.IGNORECASE)
_BLANK_LINES = re.compile(r"\n{3,}")


class PageFetchError(ValueError):
    """URL 抓取或正文提取失败。"""


def html_to_text(html: str) -> str:
    """粗糙但可预测的 HTML → 纯文本：去脚本/样式/注释，块级标签转换行，压缩空白。"""
    text = _COMMENTS.sub("", html)
    text = _SCRIPT_STYLE.sub("", text)
    text = _BLOCK_END.sub("\n", text)
    text = _TAGS.sub("", text)
    lines = [line.strip() for line in text.splitlines()]
    return _BLANK_LINES.sub("\n\n", "\n".join(line for line in lines if line)).strip()


def fetch_url_text(url: str, timeout: float = 20.0) -> str:
    if not (url.startswith("http://") or url.startswith("https://")):
        raise PageFetchError("仅支持 http/https 链接")
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
            timeout=timeout,
            follow_redirects=True,
        )
    except httpx.HTTPError as e:
        raise PageFetchError(f"网页访问失败（{e.__class__.__name__}），请直接粘贴公告全文") from e
    if resp.status_code >= 400:
        raise PageFetchError(f"网页返回 HTTP {resp.status_code}，可能需要登录或已失效，请直接粘贴公告全文")
    content_type = resp.headers.get("content-type", "")
    if "html" not in content_type and "text" not in content_type and content_type:
        raise PageFetchError(f"链接不是网页（{content_type.split(';')[0]}），请直接粘贴公告全文")
    text = html_to_text(resp.text) if "html" in content_type or "html" in resp.text[:200].lower() else resp.text.strip()
    if len(text) < MIN_TEXT_LENGTH:
        raise PageFetchError("网页正文过短或提取失败，请直接粘贴公告全文")
    return text
