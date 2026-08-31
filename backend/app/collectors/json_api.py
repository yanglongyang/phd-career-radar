"""JsonApiCollector（V0.2）：通过 mapping 配置读取公开 JSON API。

- 支持简单 dotted path（data.jobs / result.items）；
- 字段缺省返回 null 不崩溃；items 根路径错误 → source failed 并记录清晰错误；
- 不引入 JSONPath/JMESPath。
"""

from __future__ import annotations

import json

from app.collectors.base import JobCollector, RawJob
from app.collectors.config import SourceConfig
from app.collectors.http import SafeFetcher


def dotted_get(data, path: str):
    """简单 dotted path 取值；不存在返回 None。"""
    if not path:
        return None
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


class JsonApiCollector(JobCollector):
    type_name = "json_api"

    def __init__(self, source: SourceConfig):
        self.source = source
        self._fetcher = SafeFetcher(
            user_agent=source.request.user_agent, max_bytes=source.request.max_bytes
        )

    def _field(self, item: dict, key: str) -> str | None:
        value = dotted_get(item, self.source.mapping.get(key, ""))
        if value is None:
            return None
        return str(value)

    def collect(self) -> list[RawJob]:
        mapping = self.source.mapping
        items_path = mapping.get("items")
        if not items_path:
            raise ValueError(f"[{self.source.id}] mapping.items 缺失")

        _, _, body = self._fetcher.fetch(
            self.source.url,
            timeout=self.source.request.timeout_seconds,
            content_types=("json", "text"),
        )
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            raise ValueError(f"[{self.source.id}] 响应不是合法 JSON: {str(e)[:120]}") from e

        items = dotted_get(data, items_path)
        if items is None:
            raise ValueError(f"[{self.source.id}] items 路径 {items_path!r} 不存在")
        if not isinstance(items, list):
            raise ValueError(f"[{self.source.id}] items 路径 {items_path!r} 不是数组")

        results: list[RawJob] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            url = self._field(item, "url")
            results.append(
                RawJob(
                    source_id=self.source.id,
                    source_name=self.source.name,
                    title=self._field(item, "title"),
                    source_job_id=self._field(item, "source_job_id"),
                    source_url=url or "",
                    published_at_raw=self._field(item, "date"),
                    description_raw=self._field(item, "description"),
                    organization_hint=self._field(item, "organization") or self.source.organization,
                    location_hint=self._field(item, "location"),
                    raw_payload={"json_item": item},
                )
            )
        return results
