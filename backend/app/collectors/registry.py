"""CollectorRegistry（V0.2）：type → Collector 类映射。

runner 按 sources.yaml 的 enabled 清单逐 source 实例化并执行；
未知 type 在 config 解析层已报错，这里只做兜底。
"""

from __future__ import annotations

from app.collectors.base import JobCollector
from app.collectors.config import SourceConfig
from app.collectors.html_list import HtmlListCollector
from app.collectors.json_api import JsonApiCollector

_COLLECTOR_TYPES: dict[str, type[JobCollector]] = {
    "json_api": JsonApiCollector,
    "html_list": HtmlListCollector,
}


def build_collector(source: SourceConfig) -> JobCollector:
    cls = _COLLECTOR_TYPES.get(source.type)
    if cls is None:
        raise ValueError(f"[{source.id}] 未知 collector type: {source.type}")
    return cls(source)
