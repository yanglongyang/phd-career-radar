"""Collector 基类与 RawJob（V0.2，扩展 V0.1.1 的占位架构）。

Collector 只输出 RawJob（发现材料），数据库写入由 runner 完成。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.collectors.config import SourceConfig


@dataclass
class RawJob:
    """采集器产出的原始招聘材料（未结构化，一条材料 ≠ 一个正式 Job）。"""

    source_id: str
    source_name: str

    title: str | None = None
    source_job_id: str | None = None
    source_url: str = ""
    published_at_raw: str | None = None
    description_raw: str | None = None
    organization_hint: str | None = None
    location_hint: str | None = None
    sector_hint: str | None = None
    raw_payload: dict | None = field(default_factory=dict)


class JobCollector(ABC):
    """采集器基类：collect() 返回 RawJob 列表；异常由 runner 隔离。"""

    source: SourceConfig

    @abstractmethod
    def collect(self) -> list[RawJob]:
        ...
