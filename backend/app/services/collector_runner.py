"""Collector Runner（V0.2）：执行 enabled sources → RawJob → normalize → dedupe → 持久化。

关键约束（规格第九节）：
- 逐 source 独立事务提交 —— Source 失败 rollback 绝不撤销其他 Source 已落库数据；
- 单个 source 失败记录到 CollectorRunItem，不影响其余 source；
- 确定性重复（source_job_id / canonical_url / fingerprint）→ 更新 last_seen，不重建；
- possible duplicate → 只标记（possible_duplicate_of_id + reason），不自动合并；
- 关键字过滤 → filtered_count（不进库，summary 保留计数）。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors import registry as collectors_registry
from app.collectors.config import SourceConfig, keyword_filter_passes
from app.models import CollectorRun, CollectorRunItem, DiscoveredJob
from app.services.collector_dedupe import (
    canonical_url,
    content_hash,
    fingerprint,
    possible_duplicate_reason,
)


def _now() -> datetime:
    return datetime.now(UTC)


def run_collectors(
    db: Session, sources: list[SourceConfig], config_errors: list[dict] | None = None
) -> CollectorRun:
    """执行一次完整采集。逐 source 独立事务；返回 CollectorRun（含 items）。

    config_errors（P0-1）：配置解析失败的 source 也建 failed item，
    不阻塞其他正常 source。调用方负责最终 commit。"""
    config_errors = config_errors or []
    run = CollectorRun(
        started_at=_now(),
        status="running",
        trigger="manual",
        source_count=len(sources) + len(config_errors),
    )
    db.add(run)
    db.flush()

    for err in config_errors:
        item = CollectorRunItem(
            run_id=run.id,
            source_id=err.get("source_id", "?"),
            source_name=err.get("name", err.get("source_id", "?")),
            started_at=_now(),
            finished_at=_now(),
            status="failed",
            error_message=str(err.get("error", "配置错误"))[:500],
        )
        db.add(item)
        run.failed_source_count += 1
        db.flush()

    for source in sources:
        item = CollectorRunItem(
            run_id=run.id,
            source_id=source.id,
            source_name=source.name,
            started_at=_now(),
            status="running",
        )
        db.add(item)
        db.flush()
        try:
            collector = collectors_registry.build_collector(source)
            raw_jobs = collector.collect()  # 网络抓取在 savepoint 外
            # DB 写入用 savepoint 隔离：该 source 失败只回滚自己的写入，
            # 绝不撤销其他 source 已落库的数据（规格第九节事务要求）
            with db.begin_nested():
                stats = _persist_source(db, run.id, source, raw_jobs)
            item.status = "success"
            item.finished_at = _now()
            item.fetched_count = stats["fetched"]
            item.new_count = stats["new"]
            item.duplicate_count = stats["duplicate"]
            item.possible_duplicate_count = stats["possible_duplicate"]
            item.filtered_count = stats["filtered"]
        except Exception as e:  # noqa: BLE001 —— 单点失败不中断
            item.status = "failed"
            item.finished_at = _now()
            item.error_message = str(e)[:500]
            run.failed_source_count += 1
        db.flush()

    run.finished_at = _now()
    # P1-4：completed = success + failed + skipped（运行已结束就应显示完成）
    run.completed_source_count = sum(1 for i in run.items if i.status != "running")
    run.status = (
        "failed"
        if run.completed_source_count == 0 and run.source_count > 0
        else "partial_failure"
        if run.failed_source_count > 0
        else "completed"
    )
    run.discovered_count = sum(i.fetched_count for i in run.items)
    run.new_count = sum(i.new_count for i in run.items)
    run.duplicate_count = sum(i.duplicate_count for i in run.items)
    run.possible_duplicate_count = sum(i.possible_duplicate_count for i in run.items)
    run.filtered_count = sum(i.filtered_count for i in run.items)
    db.flush()
    return run


def _persist_source(
    db: Session, run_id: int, source: SourceConfig, raw_jobs
) -> dict:
    stats = {"fetched": 0, "new": 0, "duplicate": 0, "possible_duplicate": 0, "filtered": 0}
    for raw in raw_jobs:
        stats["fetched"] += 1
        searchable = f"{raw.title or ''} {raw.description_raw or ''}"
        keep, _reason = keyword_filter_passes(searchable, source.filters, source.id)
        if not keep:
            stats["filtered"] += 1
            continue

        c_url = canonical_url(raw.source_url) or None
        fp = fingerprint(raw.organization_hint, raw.title, raw.source_url)
        c_hash = content_hash(raw.description_raw, raw.title)

        # Level 1：同一 source + 同一 source_job_id → 确定重复
        existing: DiscoveredJob | None = None
        if raw.source_job_id:
            existing = db.scalars(
                select(DiscoveredJob).where(
                    DiscoveredJob.source_id == source.id,
                    DiscoveredJob.source_job_id == raw.source_job_id,
                )
            ).first()
        # Level 2：canonical URL 相同 → 确定重复（跨 source 转载也合并）
        if existing is None and c_url:
            existing = db.scalars(
                select(DiscoveredJob).where(DiscoveredJob.canonical_url == c_url)
            ).first()
        # Level 3：fingerprint 相同（同源）→ 确定重复
        if existing is None and fp and raw.source_job_id is None:
            existing = db.scalars(
                select(DiscoveredJob).where(
                    DiscoveredJob.fingerprint == fp,
                    DiscoveredJob.source_id == source.id,
                )
            ).first()

        if existing is not None:
            # 确定重复：更新 last_seen / last_run_id，不重建
            existing.last_seen_at = _now()
            existing.last_run_id = run_id
            if not existing.description_raw and raw.description_raw:
                existing.description_raw = raw.description_raw
            stats["duplicate"] += 1
            continue

        # Level 4：possible duplicate —— 同单位 + 标题高度相似 + URL 不同 → 只标记。
        # 单位以 raw.organization_hint or source.organization 为准；
        # 单位未知（两者皆空）不执行基于组织的 possible 判定（P1-5，避免
        # aggregator 上"所有 org=NULL 材料"互相误标）。
        possible_of: DiscoveredJob | None = None
        new_org = raw.organization_hint or source.organization
        if raw.title and new_org:
            same_org_rows = db.scalars(
                select(DiscoveredJob).where(
                    DiscoveredJob.organization_hint == new_org,
                )
            ).all()
            for row in same_org_rows:
                reason = possible_duplicate_reason(row.title_raw, raw.title, url_same=False)
                if reason and c_url and row.canonical_url != c_url:
                    possible_of = row
                    break

        discovered = DiscoveredJob(
            source_id=source.id,
            source_name=source.name,
            source_job_id=raw.source_job_id,
            source_url=raw.source_url,
            canonical_url=c_url,
            fingerprint=fp,
            title_raw=raw.title,
            description_raw=raw.description_raw,
            published_at_raw=raw.published_at_raw,
            organization_hint=raw.organization_hint or source.organization,
            location_hint=raw.location_hint,
            content_hash=c_hash,
            status="possible_duplicate" if possible_of else "new",
            first_run_id=run_id,
            last_run_id=run_id,
            possible_duplicate_of_id=possible_of.id if possible_of else None,
            duplicate_reason=(
                f"可能与 #{possible_of.id} 重复：{possible_duplicate_reason(possible_of.title_raw, raw.title, False)}"
                if possible_of
                else None
            ),
            raw_payload_json=raw.raw_payload,
        )
        db.add(discovered)
        db.flush()  # 立即落事务，保证同批后续条目能查到（possible duplicate 判定）
        if possible_of:
            stats["possible_duplicate"] += 1
        else:
            stats["new"] += 1
    return stats
