"""Source 配置解析与校验（V0.2）。

sources.yaml 是事实源：id 全局唯一、enabled 必须真正 boolean、
未知 type 明确报错、配置错误只影响当前 source。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import load_yaml_config

KNOWN_TYPES = {"json_api", "html_list"}

# 关键字过滤（确定性、可解释）：命中 include 才保留，命中 exclude 丢弃
DEFAULT_INCLUDE_KEYWORDS: list[str] = []
DEFAULT_EXCLUDE_KEYWORDS: list[str] = []


class SourceConfigError(ValueError):
    """单个 source 配置错误（只影响该 source）。"""


@dataclass
class RequestConfig:
    timeout_seconds: float = 15.0
    user_agent: str = "phd-career-radar/0.2 (+personal job discovery tool)"
    max_bytes: int = 5 * 1024 * 1024


@dataclass
class SourceConfig:
    id: str
    name: str
    type: str
    enabled: bool
    category: str = "other"
    organization: str | None = None
    url: str = ""
    request: RequestConfig = field(default_factory=RequestConfig)
    filters: dict = field(default_factory=dict)
    selectors: dict = field(default_factory=dict)
    detail: dict = field(default_factory=dict)
    mapping: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


def _require_type(value, expected: type, field_name: str, source_id: str) -> None:
    if not isinstance(value, expected):
        raise SourceConfigError(
            f"[{source_id}] 配置字段 {field_name} 必须是 {expected.__name__}，收到 {type(value).__name__}"
        )


def parse_source(raw: dict) -> SourceConfig:
    source_id = str(raw.get("id", "")).strip()
    if not source_id:
        raise SourceConfigError("source 缺少 id")
    name = str(raw.get("name", "")).strip() or source_id
    ctype = raw.get("type")
    _require_type(ctype, str, "type", source_id)
    if ctype not in KNOWN_TYPES:
        raise SourceConfigError(f"[{source_id}] 未知 collector type: {ctype!r}（支持 {sorted(KNOWN_TYPES)}）")
    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise SourceConfigError(f"[{source_id}] enabled 必须是 true/false，收到 {enabled!r}")
    url = raw.get("url")
    _require_type(url, str, "url", source_id)

    request_raw = raw.get("request") or {}
    _require_type(request_raw, dict, "request", source_id)
    timeout = request_raw.get("timeout_seconds", 15.0)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise SourceConfigError(f"[{source_id}] request.timeout_seconds 必须是正数")

    filters = raw.get("filters") or {}
    if not isinstance(filters, dict):
        raise SourceConfigError(f"[{source_id}] filters 必须是对象")

    for key in ("selectors", "detail", "mapping"):
        value = raw.get(key)
        if value is not None and not isinstance(value, dict):
            raise SourceConfigError(f"[{source_id}] {key} 必须是对象")

    return SourceConfig(
        id=source_id,
        name=name,
        type=ctype,
        enabled=enabled,
        category=str(raw.get("category", "other")),
        organization=raw.get("organization"),
        url=url,
        request=RequestConfig(
            timeout_seconds=float(timeout),
            user_agent=str(request_raw.get("user_agent", "phd-career-radar/0.2")),
        ),
        filters=filters,
        selectors=raw.get("selectors") or {},
        detail=raw.get("detail") or {},
        mapping=raw.get("mapping") or {},
        raw=raw,
    )


def load_sources() -> list[SourceConfig]:
    """读取 sources.yaml 全部 source（含禁用项，由 runner 决定执行哪些）。"""
    data = load_yaml_config("sources.yaml")
    raw_list = data.get("collectors") or []
    if not isinstance(raw_list, list):
        raise SourceConfigError("sources.yaml 的 collectors 必须是列表")
    return [parse_source(item) for item in raw_list]


def load_enabled_sources() -> list[SourceConfig]:
    return [s for s in load_sources() if s.enabled]


def keyword_filter_passes(
    text: str, filters: dict, source_id: str
) -> tuple[bool, str | None]:
    """确定性关键字过滤：title+description 命中任一 include 才保留；
    命中任一 exclude 丢弃。返回 (是否保留, 丢弃原因)。"""
    includes = filters.get("include_keywords") or DEFAULT_INCLUDE_KEYWORDS
    excludes = filters.get("exclude_keywords") or DEFAULT_EXCLUDE_KEYWORDS
    for key, values in (("include_keywords", includes), ("exclude_keywords", excludes)):
        if not isinstance(values, list):
            raise SourceConfigError(f"[{source_id}] filters.{key} 必须是列表")
    lowered = (text or "").lower()
    if excludes and any(str(k).lower() in lowered for k in excludes):
        return False, f"命中排除关键词: {[k for k in excludes if str(k).lower() in lowered][0]}"
    if includes and not any(str(k).lower() in lowered for k in includes):
        return False, "未命中任何包含关键词"
    return True, None
