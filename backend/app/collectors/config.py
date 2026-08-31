"""Source 配置解析与校验（V0.2）。

sources.yaml 是事实源：id 全局唯一、enabled 必须真正 boolean、
未知 type 明确报错、配置错误只影响当前 source。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

import yaml

from app.core.config import CONFIG_DIR

KNOWN_TYPES = {"json_api", "html_list"}

# 列表页日期格式多种多样（2026.08.24 / 2023-07-05 / 发布日期：2016-11-29 / 2025年9月8日），
# 统一按"第一个完整日期"提取；用于 max_age_days 过期岗位过滤。
_DATE_PATTERN = re.compile(r"(?P<y>\d{4})[-/.年](?P<m>\d{1,2})[-/.月](?P<d>\d{1,2})日?")


def extract_date_text(raw: str | None) -> str | None:
    """从任意文本提取第一个完整日期串（如 "2026.08.24" / "2016-11-29"），无则 None。"""
    if not raw:
        return None
    m = _DATE_PATTERN.search(raw)
    return m.group(0) if m else None


def parse_date_from_text(raw: str | None) -> date | None:
    """从任意文本解析第一个完整日期（YYYY[-/.年]M[-/.月]D），返回 date 或 None。

    只认 4 位年份 + 月 + 日：HUST 标题里的"2025年专任教师招聘"（无月日）不会误匹配。"""
    if not raw:
        return None
    m = _DATE_PATTERN.search(raw)
    if not m:
        return None
    try:
        return date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
    except ValueError:
        return None

# 关键字过滤（确定性、可解释）：命中 include 才保留，命中 exclude 丢弃
DEFAULT_INCLUDE_KEYWORDS: list[str] = []
DEFAULT_EXCLUDE_KEYWORDS: list[str] = []

# 招聘标题特征词：HtmlListCollector 列表页常混入导航/新闻动态，
# 标题不含任一特征词的材料视为明显无关（pre-filter，非职业评价）。
DEFAULT_TITLE_REQUIRE_WORDS = [
    "招聘", "诚聘", "诚邀", "招贤", "引进", "招收", "招录",
    "博士后", "岗位", "教师", "研究员", "副研究员", "助理研究员",
    "科研助理", "教授", "副教授", "讲师", "人才", "招聘公告",
    "招聘启事", "offer", "position", "recruit", "faculty",
]


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
    max_age_days: int | None = None
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

    max_age_days = raw.get("max_age_days")
    if max_age_days is not None:
        if not isinstance(max_age_days, int) or isinstance(max_age_days, bool) or max_age_days <= 0:
            raise SourceConfigError(f"[{source_id}] max_age_days 必须是正整数（天数）")

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
        max_age_days=max_age_days,
        raw=raw,
    )


def _read_sources_yaml() -> dict:
    """读取 sources.yaml（每次调用都重新读取 —— Collector 配置需要频繁调整，
    不走 load_yaml_config 的长期 LRU cache，P1-6）。"""
    path = CONFIG_DIR / "sources.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_sources() -> tuple[list[SourceConfig], list[dict]]:
    """逐条解析（P0-1）：单个配置错误不阻塞其他 source。

    返回 (valid_sources, config_errors)。config_errors 元素：
    {source_id, name, error}；id 缺失时 source_id 用占位。"""
    data = _read_sources_yaml()
    raw_list = data.get("collectors") or []
    valid: list[SourceConfig] = []
    errors: list[dict] = []
    seen_ids: set[str] = set()
    if not isinstance(raw_list, list):
        return [], [{"source_id": "?", "name": "sources.yaml", "error": "collectors 必须是列表"}]
    for index, item in enumerate(raw_list):
        if not isinstance(item, dict):
            errors.append({"source_id": f"item#{index}", "name": f"item#{index}",
                           "error": "source 必须是对象"})
            continue
        source_id = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip() or source_id or f"item#{index}"
        # id 全局唯一（Final closure）：先登记非空 id 再解析 ——
        # 即使第一个同名 source 配置失败，后续同名 source 也不能合法执行
        if source_id:
            if source_id in seen_ids:
                errors.append({"source_id": source_id, "name": name,
                               "error": f"source id 重复: {source_id!r}（id 必须全局唯一）"})
                continue
            seen_ids.add(source_id)
        try:
            parsed = parse_source(item)
        except SourceConfigError as e:
            errors.append({"source_id": source_id or f"item#{index}", "name": name,
                           "error": str(e)})
            continue
        valid.append(parsed)
    return valid, errors


def load_enabled_sources() -> tuple[list[SourceConfig], list[dict]]:
    valid, errors = load_sources()
    return [s for s in valid if s.enabled], errors


def ensure_sources_schema() -> dict:
    """legacy V0.1.1 sources.yaml → V0.2 迁移（P1-7）：
    无 schema_version 且 collectors 为空的旧文件 → 备份 + 复制 bundled 默认配置；
    已有版本号或用户主动清空（有版本号）则尊重，不覆盖。"""
    path = CONFIG_DIR / "sources.yaml"
    data = _read_sources_yaml()
    version = data.get("schema_version")
    collectors = data.get("collectors")
    if version is not None:
        return {"migrated": False, "reason": "已有版本"}
    # 无版本：legacy 文件。若为空列表 → 迁移到 bundled 默认（若存在且不是同一文件）
    if isinstance(collectors, list) and len(collectors) == 0:
        from app.core.config import RESOURCE_ROOT

        bundled_path = RESOURCE_ROOT / "config" / "sources.yaml"
        if bundled_path.exists() and bundled_path.resolve() != path.resolve():
            import shutil

            shutil.copy2(path, CONFIG_DIR / "sources.yaml.legacy.bak")
            with bundled_path.open("r", encoding="utf-8") as f:
                bundled_data = yaml.safe_load(f) or {}
            bundled_data.setdefault("schema_version", 2)
            path.write_text(
                yaml.safe_dump(bundled_data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            return {"migrated": True, "reason": "legacy 空配置已迁移到 V0.2 默认 sources"}
    return {"migrated": False, "reason": "无需迁移"}


def title_require_filter(title: str | None, custom_words: list[str] | None) -> bool:
    """标题必须包含至少一个招聘特征词（可配置覆盖）。"""
    words = custom_words if custom_words is not None else DEFAULT_TITLE_REQUIRE_WORDS
    lowered = (title or "").lower()
    return any(str(w).lower() in lowered for w in words)


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
