"""风评聚合服务（Phase 6）——确定性统计层。

**Evidence 是事实资产，Reputation 是基于 Evidence 的派生分析。** 本模块只做
确定性计算，三件必须锁死的事：

1. **unknown scope 不自动升级成"全校通用证据"**：scope 未标明的证据只作情报
   线索（clues），不进入任何主题的计量统计；
2. **单条/低等级帖子是线索，不是定量评分依据**：主题要 `eligible_for_scoring`
   必须满足"独立来源 ≥ 2 且等级分布含 A/B"；单源或纯 C/D 主题保持 ineligible；
3. **来源数、独立来源数、等级、时间跨度全部由 backend 计算**：AI 只做主题
   叙述综合（见 ai/schemas.ReputationSynthesisOut），数字不由模型产生。

独立性判定：`independence_key` 相同的证据视为同一信息源（含其转载）；
未标记 key 的证据各自独立成源；`repost_of_evidence_id` 指向的转载跟随源头，
不单独计数。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.provider import LLMProvider
from app.core.fingerprint import normalize_text
from app.models import Evidence, Organization
from app.schemas.reputation import (
    ReputationClueItem,
    ReputationReportOut,
    ReputationTopicStat,
)

REPUTATION_TOPICS = (
    "assessment_pressure",
    "salary_fulfillment",
    "startup_funding_fulfillment",
    "administrative_burden",
    "teaching_load",
    "young_faculty_turnover",
    "promotion_environment",
    "department_management",
    "research_collaboration",
    "student_resources",
    "other",
)

# 进入定量评分的最低门槛（Phase 6 策略，代码即文档）
MIN_INDEPENDENT_SOURCES = 2
ELIGIBLE_LEVELS = ("A", "B")

LEVEL_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}


def _now() -> datetime:
    return datetime.now(UTC)


def collect_evidence(
    db: Session, organization_id: int, department: str | None = None
) -> tuple[list[Evidence], list[tuple[Evidence, str]]]:
    """收集某单位（可选限定院系）的风评证据。

    返回 (可计量证据, 情报线索及原因)：
    - 组织级 scope（organization）→ 可计量；
    - 院系 scope：未限定院系时纳入；限定时要求 scope_name 匹配，否则降为线索；
    - unknown / lab scope、绑定具体岗位的证据 → 线索（不猜归属、岗位级不进校级）。
    """
    rows = db.scalars(
        select(Evidence)
        .where(Evidence.organization_id == organization_id)
        .order_by(Evidence.id)
    ).all()
    eligible: list[Evidence] = []
    clues: list[tuple[Evidence, str]] = []
    dept_norm = normalize_text(department) if department else None
    for ev in rows:
        if ev.job_id is not None:
            clues.append((ev, "岗位级证据，不进入单位级风评统计"))
            continue
        if ev.scope_level == "organization":
            eligible.append(ev)
        elif ev.scope_level == "department":
            if department is None:
                eligible.append(ev)
            elif ev.scope_name and dept_norm and normalize_text(ev.scope_name) == dept_norm:
                eligible.append(ev)
            else:
                clues.append((ev, "院系级证据与所查询院系不匹配"))
        elif ev.scope_level == "unknown":
            clues.append((ev, "scope 未标明：不能自动升级为全校通用证据，仅作情报线索"))
        elif ev.scope_level == "lab":
            clues.append((ev, "实验室级证据：当前岗位/单位没有 lab 身份，不猜归属"))
        else:
            clues.append((ev, f"未知 scope_level: {ev.scope_level}"))
    return eligible, clues


def _independent_groups(rows: list[Evidence]) -> list[list[Evidence]]:
    """按 independence_key 分组：同 key 同源；无 key 自成一源；
    转载跟随其源头证据的分组，不单独计数。"""
    rows_by_id = {ev.id: ev for ev in rows}

    def source_key(ev: Evidence, seen: frozenset[int] = frozenset()) -> str:
        if ev.independence_key:
            return ev.independence_key
        if ev.repost_of_evidence_id and ev.repost_of_evidence_id in rows_by_id and ev.repost_of_evidence_id not in seen:
            return source_key(rows_by_id[ev.repost_of_evidence_id], seen | {ev.id})
        return f"evidence_{ev.id}"

    groups: dict[str, list[Evidence]] = defaultdict(list)
    for ev in rows:
        groups[source_key(ev)].append(ev)
    # 组间按首条 id 排序、组内按 id 排序，保证输出稳定
    return [sorted(g, key=lambda e: e.id) for _, g in sorted(groups.items())]


def _group_stance(group: list[Evidence]) -> str:
    stances = {ev.stance for ev in group}
    if "negative" in stances:
        return "negative"
    if "positive" in stances:
        return "positive"
    return "other"


def _eligible_reason(independent: int, levels: set[str]) -> str:
    if independent >= MIN_INDEPENDENT_SOURCES and any(lv in ELIGIBLE_LEVELS for lv in levels):
        return (
            f"独立来源 {independent} 个且等级分布含 A/B —— 可作为定量风评依据"
        )
    reasons = []
    if independent < MIN_INDEPENDENT_SOURCES:
        reasons.append(f"独立来源仅 {independent} 个（< {MIN_INDEPENDENT_SOURCES}）")
    if not any(lv in ELIGIBLE_LEVELS for lv in levels):
        reasons.append("等级分布仅含 C/D，缺乏较可靠来源")
    return "；".join(reasons) + " —— 仅作情报参考，不进入定量评分"


def aggregate_topics(eligible_rows: list[Evidence]) -> list[ReputationTopicStat]:
    by_topic: dict[str, list[Evidence]] = defaultdict(list)
    for ev in eligible_rows:
        topic = ev.category if ev.category in REPUTATION_TOPICS else "other"
        by_topic[topic].append(ev)

    stats: list[ReputationTopicStat] = []
    for topic in sorted(by_topic):
        rows = by_topic[topic]
        groups = _independent_groups(rows)
        positive = sum(1 for g in groups if _group_stance(g) == "positive")
        negative = sum(1 for g in groups if _group_stance(g) == "negative")
        levels = sorted({ev.evidence_level for ev in rows}, key=lambda lv: LEVEL_ORDER.get(lv, 9))
        dates = [ev.published_at for ev in rows if ev.published_at]
        independent = len(groups)
        eligible = independent >= MIN_INDEPENDENT_SOURCES and any(
            lv in ELIGIBLE_LEVELS for lv in levels
        )
        stats.append(
            ReputationTopicStat(
                topic=topic,
                positive_sources=positive,
                negative_sources=negative,
                independent_sources=independent,
                evidence_levels=levels,
                time_start=min(dates).isoformat() if dates else None,
                time_end=max(dates).isoformat() if dates else None,
                eligible_for_scoring=eligible,
                eligible_reason=_eligible_reason(independent, levels),
                evidence_ids=[ev.id for ev in rows],
            )
        )
    return stats


def build_report(
    db: Session,
    organization: Organization,
    department: str | None = None,
) -> ReputationReportOut:
    """纯确定性风评报告（不含 AI 结论）。"""
    eligible_rows, clues = collect_evidence(db, organization.id, department)
    topics = aggregate_topics(eligible_rows)
    overall = "medium" if any(t.eligible_for_scoring for t in topics) else "low"
    return ReputationReportOut(
        organization_id=organization.id,
        organization_name=organization.name,
        department=department,
        topics=topics,
        clues=[
            ReputationClueItem(evidence_id=ev.id, claim=ev.claim, reason=reason)
            for ev, reason in clues
        ],
        overall_confidence=overall,
        synthesized_by_ai=False,
        generated_at=_now(),
    )


def synthesize_report(
    db: Session,
    organization: Organization,
    provider: LLMProvider,
    department: str | None = None,
) -> ReputationReportOut:
    """确定性统计 + AI 主题叙述综合：AI 只写 conclusion，数字一律来自统计层。"""
    report = build_report(db, organization, department)
    eligible_rows, _ = collect_evidence(db, organization.id, department)

    context = {
        "organization_name": organization.name,
        "evidence": [
            {
                "id": ev.id,
                "claim": ev.claim,
                "category": ev.category,
                "evidence_level": ev.evidence_level,
                "stance": ev.stance,
                "is_firsthand": ev.is_firsthand,
                "independence_key": ev.independence_key,
                "source_type": ev.source_type,
                "published_at": str(ev.published_at) if ev.published_at else None,
            }
            for ev in eligible_rows
        ],
        "statistics": [t.model_dump(exclude={"ai_conclusion"}) for t in report.topics],
    }
    synthesis, prompt_version = provider.summarize_reputation(context)

    conclusions = {t.topic: t.conclusion for t in synthesis.topics}
    for stat in report.topics:
        if stat.topic in conclusions:
            stat.ai_conclusion = conclusions[stat.topic]
    report.synthesized_by_ai = True
    report.prompt_version = prompt_version
    report.overall_confidence = synthesis.confidence if synthesis.confidence != "low" else report.overall_confidence
    return report
