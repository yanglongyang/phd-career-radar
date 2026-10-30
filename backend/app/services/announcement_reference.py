"""Evidence-preserving metadata for current and historical recruitment notices.

The year comes from the notice title or its publication date, never the crawl
date. Snippets are verbatim excerpts, not promises or AI-generated facts.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from app.collectors.config import parse_date_from_text

YEAR_PATTERN = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
REQUIREMENT_WORDS = (
    "招聘条件", "应聘条件", "基本条件", "岗位要求", "任职要求", "专业要求", "学历", "学位",
    "年龄", "博士", "专业", "资格", "研究方向", "科研成果", "工作经验", "临床", "医师",
)
BENEFIT_WORDS = (
    "待遇", "福利", "薪酬", "薪资", "年薪", "月薪", "工资", "安家", "住房", "购房", "补贴", "补助", "津贴",
    "启动经费", "科研经费", "科研启动", "编制", "聘期", "服务期", "违约", "考核", "一事一议",
)


def current_year() -> int:
    # China uses UTC+8 without seasonal changes; Windows bundles need no IANA
    # timezone database merely to determine the current recruitment year.
    return datetime.now(timezone(timedelta(hours=8))).year


def announcement_year(title: str | None, published: str | None) -> tuple[int | None, str]:
    years = {int(v) for v in YEAR_PATTERN.findall(title or "")}
    # Campus jobs often say “26届” while being published during 2025.
    years.update(2000 + int(v) for v in re.findall(r"(?<!\d)(\d{2})届", title or ""))
    if len(years) == 1:
        return years.pop(), "title"
    if len(years) > 1:
        # Multiple years can denote a cohort or a reprint; do not guess.
        return None, "ambiguous_title"
    parsed = parse_date_from_text(published)
    return (parsed.year, "published_at") if parsed else (None, "unknown")


def reference_status(year: int | None, today_year: int | None = None) -> str:
    now = today_year or current_year()
    if year is None:
        return "unknown"
    if year < now:
        return "historical"
    return "current_year" if year == now else "upcoming"


def excerpt(text: str | None, words: tuple[str, ...], limit: int = 2400) -> str | None:
    if not text:
        return None
    # Preserve paragraphs/tables where possible. Split oversized paragraphs at
    # sentence boundaries, without converting amounts or inferring totals.
    lines = [v.strip() for v in re.split(r"[\r\n]+|(?<=[。；;])", text) if v.strip()]
    chosen: list[str] = []
    seen: set[str] = set()
    used = 0
    for line in lines:
        if not any(word in line for word in words) or line in seen:
            continue
        seen.add(line)
        remaining = limit - used
        if remaining <= 0:
            break
        chosen.append(line[:remaining])
        used += len(chosen[-1]) + 1
    return "\n".join(chosen) or None


def infer_organization(title: str | None, organizations: list | None = None) -> str | None:
    """Match configured employer names only; a government publisher is not one."""
    for name in sorted((v for v in (organizations or []) if isinstance(v, str)), key=len, reverse=True):
        if name in (title or ""):
            return name
    return None


def reference_notice(year: int | None) -> str | None:
    if reference_status(year) == "historical":
        return f"{year} 年历史公告，仅供条件、待遇和招聘节奏参考；不代表当前在招或今年继续执行。"
    return None


def backfill_reference_metadata(engine) -> int:
    """Upgrade existing Inbox rows without altering employer/sector or CRM data."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.models import DiscoveredJob

    changed = 0
    with Session(engine) as db:
        rows = db.scalars(select(DiscoveredJob).where(
            DiscoveredJob.announcement_year.is_(None) | DiscoveredJob.province.is_(None)
        ))
        for row in rows:
            known_shanxi = row.source_id in {"sxu_faculty", "sxicc_gcc", "sxicc_bsh"}
            province_changed = known_shanxi and row.province is None
            if province_changed:
                row.province = "山西"
            year, origin = announcement_year(row.title_raw, row.published_at_raw)
            payload = dict(row.raw_payload_json or {})
            if payload.get("year_source") == origin and year is None:
                if province_changed:
                    changed += 1
                continue
            if row.announcement_year is not None:
                if province_changed:
                    changed += 1
                continue
            row.announcement_year = year
            row.requirements_summary = excerpt(row.description_raw, REQUIREMENT_WORDS)
            row.benefits_summary = excerpt(row.description_raw, BENEFIT_WORDS)
            payload["year_source"] = origin
            row.raw_payload_json = payload
            changed += 1
        db.commit()
    return changed
