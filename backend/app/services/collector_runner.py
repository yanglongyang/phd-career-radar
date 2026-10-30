"""Collector Runner（V0.2）：执行 enabled sources → RawJob → normalize → dedupe → 持久化。

关键约束（规格第九节）：
- 逐 source 独立事务提交 —— Source 失败 rollback 绝不撤销其他 Source 已落库数据；
- 单个 source 失败记录到 CollectorRunItem，不影响其余 source；
- 确定性重复（source_job_id / canonical_url / fingerprint）→ 更新 last_seen，不重建；
- possible duplicate → 只标记（possible_duplicate_of_id + reason），不自动合并；
- 关键字过滤 → filtered_count（不进库，summary 保留计数）。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors import registry as collectors_registry
from app.collectors.config import (
    SourceConfig,
    keyword_filter_passes,
    parse_date_from_text,
)
from app.models import CollectorRun, CollectorRunItem, DiscoveredJob
from app.services.announcement_reference import (
    BENEFIT_WORDS,
    REQUIREMENT_WORDS,
    announcement_year,
    current_year,
    excerpt,
    infer_organization,
)
from app.services.collector_dedupe import (
    canonical_url,
    content_hash,
    fingerprint,
    possible_duplicate_reason,
)


def _now() -> datetime:
    return datetime.now(UTC)


def run_collectors(
    db: Session, sources: list[SourceConfig], config_errors: list[dict] | None = None,
    *, mode: str = "recent", history_years: int = 3, trigger: str = "manual",
    province: str | None = None,
) -> CollectorRun:
    """执行一次完整采集。逐 source 独立事务；返回 CollectorRun（含 items）。

    config_errors（P0-1）：配置解析失败的 source 也建 failed item，
    不阻塞其他正常 source。调用方负责最终 commit。"""
    config_errors = config_errors or []
    run = CollectorRun(
        started_at=_now(),
        status="running",
        trigger=trigger,
        mode=mode,
        history_years=history_years if mode == "history" else None,
        province=province,
        source_count=len(sources) + len(config_errors),
    )
    db.add(run)
    db.flush()

    for err in config_errors:
        item = CollectorRunItem(
            run_id=run.id,
            source_id=err.get("source_id", "?"),
            source_name=err.get("name", err.get("source_id", "?")),
            sector=err.get("sector", "other"),
            started_at=_now(),
            finished_at=_now(),
            status="failed",
            error_message=str(err.get("error", "配置错误"))[:500],
        )
        db.add(item)
        run.failed_source_count += 1
        db.flush()

    db.commit()  # Make the run visible while network requests are in progress.
    for original_source in sources:
        source = replace(original_source, scope=mode, history={**original_source.history, "years": history_years})
        item = CollectorRunItem(
            run_id=run.id,
            source_id=source.id,
            source_name=source.name,
            sector=source.sector,
            started_at=_now(),
            status="running",
        )
        db.add(item)
        db.flush()
        db.commit()  # Do not hold a SQLite write transaction during HTTP I/O.
        try:
            collector = collectors_registry.build_collector(source)
            raw_jobs = collector.collect()  # 网络抓取在 savepoint 外
            # DB 写入用 savepoint 隔离：该 source 失败只回滚自己的写入，
            # 绝不撤销其他 source 已落库的数据（规格第九节事务要求）
            with db.begin_nested():
                stats = _persist_source(db, run.id, source, raw_jobs, mode=mode, history_years=history_years)
            warnings = getattr(collector, "warnings", [])
            item.status = "partial_failure" if warnings else "success"
            item.warning_count = len(warnings)
            if warnings:
                item.error_message = "; ".join(str(w) for w in warnings)[:500]
            item.finished_at = _now()
            item.fetched_count = stats["fetched"]
            item.new_count = stats["new"]
            item.duplicate_count = stats["duplicate"]
            item.possible_duplicate_count = stats["possible_duplicate"]
            item.filtered_count = stats["filtered"]
            prefiltered = getattr(collector, "prefiltered_count", 0)
            item.fetched_count += prefiltered
            item.filtered_count += prefiltered
            item.recency_skipped_count = stats["recency_skipped"]
            recency_prefiltered = getattr(collector, "recency_prefiltered_count", 0)
            item.fetched_count += recency_prefiltered
            item.recency_skipped_count += recency_prefiltered
        except Exception as e:  # noqa: BLE001 —— 单点失败不中断
            item.status = "failed"
            item.finished_at = _now()
            item.error_message = str(e)[:500]
            run.failed_source_count += 1
        db.flush()
        # Each source survives interruption/failure of a later source.
        completed_items = db.scalars(select(CollectorRunItem).where(CollectorRunItem.run_id == run.id)).all()
        run.completed_source_count = sum(i.status != "running" for i in completed_items)
        for field_name, item_name in (
            ("discovered_count", "fetched_count"), ("new_count", "new_count"),
            ("duplicate_count", "duplicate_count"), ("possible_duplicate_count", "possible_duplicate_count"),
            ("filtered_count", "filtered_count"), ("recency_skipped_count", "recency_skipped_count"),
        ):
            setattr(run, field_name, sum(getattr(i, item_name) for i in completed_items))
        db.commit()

    run.finished_at = _now()
    # P1-4：completed = success + failed + skipped（运行已结束就应显示完成）
    run.completed_source_count = sum(1 for i in run.items if i.status != "running")
    # Final closure：全部 source 失败 → failed；部分失败 → partial_failure
    if run.source_count > 0 and run.failed_source_count == run.source_count:
        run.status = "failed"
    elif run.failed_source_count > 0 or any(i.warning_count for i in run.items):
        run.status = "partial_failure"
    else:
        run.status = "completed"
    run.discovered_count = sum(i.fetched_count for i in run.items)
    run.new_count = sum(i.new_count for i in run.items)
    run.duplicate_count = sum(i.duplicate_count for i in run.items)
    run.possible_duplicate_count = sum(i.possible_duplicate_count for i in run.items)
    run.filtered_count = sum(i.filtered_count for i in run.items)
    run.recency_skipped_count = sum(i.recency_skipped_count for i in run.items)
    db.flush()
    return run


def _recency_skipped(source: SourceConfig, raw) -> bool:
    """max_age_days 过期过滤：列表页常混入多年前的旧岗位（2023/2016），
    发布日期早于 max_age_days 的直接跳过，不再进 Inbox。

    无法解析日期时 fail-open（不因过期跳过）——宁可保留待人工判断。"""
    if not source.max_age_days:
        return False
    published = parse_date_from_text(raw.published_at_raw)
    if published is None:
        return False
    return (_now().date() - published).days > source.max_age_days


def _persist_source(
    db: Session, run_id: int, source: SourceConfig, raw_jobs,
    *, mode: str = "recent", history_years: int = 3,
) -> dict:
    stats = {
        "fetched": 0, "new": 0, "duplicate": 0,
        "possible_duplicate": 0, "filtered": 0, "recency_skipped": 0,
    }
    for raw in raw_jobs:
        stats["fetched"] += 1
        searchable = f"{raw.title or ''} {raw.description_raw or ''}"
        # Recruitment notices normally contain interview/medical-check/public
        # notice procedures. Those words exclude follow-up *titles*, not whole
        # recruitment documents containing those procedures.
        includes = {"include_keywords": source.filters.get("include_keywords", [])}
        excludes = {"exclude_keywords": [
            *source.filters.get("exclude_keywords", []), *source.filters.get("exclude_title_keywords", []),
        ]}
        keep, _reason = keyword_filter_passes(searchable, includes, source.id)
        exclusion_text = searchable if source.filters.get("exclude_scope") == "content" else raw.title or ""
        not_excluded, _reason = keyword_filter_passes(exclusion_text, excludes, source.id)
        if not keep or not not_excluded:
            stats["filtered"] += 1
            continue
        year, year_source = announcement_year(raw.title, raw.published_at_raw)
        old = _recency_skipped(source, raw) if mode == "recent" else (
            year is not None and not current_year() - history_years <= year < current_year()
        )
        if old:
            stats["recency_skipped"] += 1
            continue

        c_url = canonical_url(raw.source_url) or None
        fp = fingerprint(raw.organization_hint, raw.title, raw.source_url)
        c_hash = content_hash(raw.description_raw, raw.title)
        employer = raw.organization_hint or source.organization or infer_organization(
            raw.title, source.raw.get("organizations")
        )
        payload = dict(raw.raw_payload or {})
        payload["year_source"] = year_source
        payload["collection_mode"] = mode
        requirements = excerpt(raw.description_raw, REQUIREMENT_WORDS)
        benefits = excerpt(raw.description_raw, BENEFIT_WORDS)

        # Level 1：同一 source + 同一 source_job_id → 确定重复
        existing: DiscoveredJob | None = None
        # A static URL can be reused for an annual notice. Prefer a same-year
        # snapshot, including archived ones, before resolving the current URL.
        if c_url and year:
            existing = db.scalars(select(DiscoveredJob).where(
                ((DiscoveredJob.url_identity == c_url) | (DiscoveredJob.canonical_url == c_url)),
                DiscoveredJob.announcement_year == year,
            )).first()
        if existing is None and raw.source_job_id:
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

        if existing is not None and year and existing.announcement_year and existing.announcement_year != year:
            # Freeze the old year/requirements/benefits as one coherent record.
            # The new annual notice receives its own Inbox review status.
            existing.url_identity = existing.url_identity or existing.canonical_url or c_url
            existing.canonical_url = None
            old_payload = dict(existing.raw_payload_json or {})
            old_payload["archived_reason"] = "同一公告链接已发布不同年度内容，原年度正文保留"
            if existing.source_job_id and existing.source_id == source.id:
                old_payload["original_source_job_id"] = existing.source_job_id
                existing.source_job_id = f"{existing.source_job_id[:110]}@{existing.announcement_year}"
            existing.raw_payload_json = old_payload
            db.flush()
            existing = None

        if existing is not None:
            # 确定重复：更新 last_seen / last_run_id，不重建
            existing.last_seen_at = _now()
            existing.last_run_id = run_id
            existing.url_identity = existing.url_identity or c_url
            if raw.description_raw and (
                not existing.description_raw or payload.get("detail_status") == "complete"
            ):
                existing.description_raw = raw.description_raw
                existing.title_raw = raw.title or existing.title_raw
                existing.published_at_raw = raw.published_at_raw or existing.published_at_raw
                existing.content_hash = c_hash
                existing.requirements_summary = requirements
                existing.benefits_summary = benefits
                existing.raw_payload_json = {**(existing.raw_payload_json or {}), **payload}
            elif payload.get("detail_status") in ("failed", "missing") and existing.description_raw:
                existing.raw_payload_json = {
                    **(existing.raw_payload_json or {}),
                    "last_fetch_error": payload.get("detail_error") or "本次正文未能完整抓取，保留上次正文",
                }
            elif not existing.raw_payload_json:
                existing.raw_payload_json = payload
            if existing.announcement_year is None:
                existing.announcement_year = year
            if not existing.province:
                existing.province = source.province
            if not existing.organization_hint:
                existing.organization_hint = employer
            if not existing.location_hint:
                existing.location_hint = raw.location_hint or source.location or source.province
            stats["duplicate"] += 1
            continue

        # Level 4：possible duplicate —— 同单位 + 标题高度相似 + URL 不同 → 只标记。
        # 单位以 raw.organization_hint or source.organization 为准；
        # 单位未知（两者皆空）不执行基于组织的 possible 判定（P1-5，避免
        # aggregator 上"所有 org=NULL 材料"互相误标）。
        possible_of: DiscoveredJob | None = None
        new_org = employer
        if raw.title and new_org:
            same_org_rows = db.scalars(
                select(DiscoveredJob).where(
                    DiscoveredJob.organization_hint == new_org,
                )
            ).all()
            for row in same_org_rows:
                # An employer's 2024 and 2025 annual notices are different
                # reference material, even when their titles are very similar.
                if year and row.announcement_year and row.announcement_year != year:
                    continue
                reason = possible_duplicate_reason(row.title_raw, raw.title, url_same=False)
                if reason and c_url and row.canonical_url != c_url:
                    possible_of = row
                    break

        discovered = DiscoveredJob(
            source_id=source.id,
            source_name=source.name,
            # V0.3：来源/单位性质在发现时冻结 —— raw.sector_hint（mixed 源逐条确定时）
            # 优先，否则取 source.sector；之后修改 sources.yaml 不回溯历史语义。
            sector=raw.sector_hint or source.sector,
            source_job_id=raw.source_job_id,
            source_url=raw.source_url,
            canonical_url=c_url,
            url_identity=c_url,
            fingerprint=fp,
            title_raw=raw.title,
            description_raw=raw.description_raw,
            published_at_raw=raw.published_at_raw,
            announcement_year=year,
            province=source.province,
            requirements_summary=requirements,
            benefits_summary=benefits,
            organization_hint=employer,
            location_hint=raw.location_hint or source.location or source.province,
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
            raw_payload_json=payload,
        )
        db.add(discovered)
        db.flush()  # 立即落事务，保证同批后续条目能查到（possible duplicate 判定）
        if possible_of:
            stats["possible_duplicate"] += 1
        else:
            stats["new"] += 1
    return stats
