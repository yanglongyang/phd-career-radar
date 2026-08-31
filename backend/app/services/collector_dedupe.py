"""Collector 去重引擎（V0.2，独立于 Collector 与 runner）。

Precision over Recall：确定重复才自动去重；模糊重复只标记 possible。
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"}


def canonical_url(url: str) -> str:
    """URL canonicalization（Level 2）：
    - 去除 fragment；trailing slash 标准化（保留 path 根）；
    - scheme/host 小写、去默认端口；
    - 移除常见 tracking query（utm_*）；**其余 query 参数保留**
      （招聘系统 query 可能代表职位 ID，不得随意删除）。"""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = parts.hostname.lower() if parts.hostname else ""
    port = parts.port
    default_port = {"http": 80, "https": 443}.get(scheme)
    if port and port == default_port:
        netloc = host
    else:
        netloc = f"{host}:{port}" if port else host
    path = parts.path
    if path and path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    if not path:
        path = "/"
    query = urlencode(
        sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS)
    )
    return urlunsplit((scheme, netloc, path, query, ""))


_PUNCT = re.compile(r"[\s，。、；：！？（）()【】\[\]「」·\-—_/\\,.:;!?#'\"*]+")


def _normalize(text: str | None) -> str:
    return _PUNCT.sub("", (text or "")).lower()


def fingerprint(organization_hint: str | None, title: str | None, url: str) -> str | None:
    """Level 3 确定性指纹：normalize(org) + normalize(title) + canonical path。"""
    if not title:
        return None
    path = urlsplit(canonical_url(url)).path
    raw = f"{_normalize(organization_hint)}|{_normalize(title)}|{path}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def content_hash(description: str | None, title: str | None) -> str | None:
    if not description and not title:
        return None
    raw = f"{_normalize(title)}|{_normalize(description)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def title_similarity(a: str | None, b: str | None) -> float:
    from difflib import SequenceMatcher

    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def possible_duplicate_reason(existing_title: str, new_title: str, url_same: bool) -> str | None:
    """Level 4：同单位 + 同标题高度一致 + URL 不同 → 疑似重复（只标记不合并）。"""
    if url_same:
        return None
    sim = title_similarity(existing_title, new_title)
    if sim >= 0.8:
        return f"标题高度相似（相似度 {sim:.0%}）但 URL 不同"
    return None
