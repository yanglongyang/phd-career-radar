"""JobCollector 抽象（Phase 7 架构占位）。

V0.1 不实现任何真实爬虫 —— 只定义契约，保证未来接入时：
- 每个 collector 返回 RawJob 列表（未归一化）；
- 单个 collector 抛错被 registry 捕获，不影响其他 collector；
- 启用状态来自 config/sources.yaml（enabled 字段）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RawJob:
    """采集器产出的原始岗位（未结构化）。"""

    title: str
    source: str
    source_job_id: str | None = None
    source_url: str | None = None
    description_raw: str | None = None
    extra: dict = field(default_factory=dict)


class JobCollector(ABC):
    """采集器基类：collect() 返回原始岗位列表；异常由 registry 隔离。"""

    name: str = "base"
    job_categories: tuple[str, ...] = ("other",)

    @abstractmethod
    def collect(self) -> list[RawJob]:
        ...


class CollectorRegistry:
    """按 sources.yaml 的 enabled 清单执行；单点失败不中断整体。"""

    def __init__(self) -> None:
        self._collectors: dict[str, JobCollector] = {}

    def register(self, collector: JobCollector) -> None:
        self._collectors[collector.name] = collector

    def run_enabled(self, enabled_names: list[str]) -> dict:
        results: dict[str, list[RawJob]] = {}
        errors: dict[str, str] = {}
        for name in enabled_names:
            collector = self._collectors.get(name)
            if collector is None:
                errors[name] = "未注册的 collector"
                continue
            try:
                results[name] = collector.collect()
            except Exception as e:  # noqa: BLE001 -- 单点失败不中断
                errors[name] = str(e)[:300]
        return {"results": results, "errors": errors}
