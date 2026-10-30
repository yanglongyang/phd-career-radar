"""One-shot collection for an existing local/server installation.

Example: python -m app.collect --mode history --province 山西 --history-years 3
Run from backend/ with the application's virtual environment.
"""

import argparse
import json

from sqlalchemy.orm import Session

from app.collectors.config import load_enabled_sources
from app.db.base import Base
from app.db.migrate import ensure_missing_columns
from app.db.session import engine
from app.schemas.collector import CollectorRunRequest
from app.services.announcement_reference import backfill_reference_metadata
from app.services.collector_tasks import CollectorBusyError, RunLease, execute, select_sources


def main() -> int:
    parser = argparse.ArgumentParser(description="招聘更新或历年公告补抓（不会调用AI或自动投递）")
    parser.add_argument("--mode", choices=("recent", "history"), default="recent")
    parser.add_argument("--province", default="山西", help="来源地区；空字符串表示全部地区")
    parser.add_argument("--history-years", type=int, default=3)
    parser.add_argument("--source", action="append", dest="source_ids", help="只采指定来源，可重复")
    args = parser.parse_args()
    options = CollectorRunRequest(
        mode=args.mode, province=args.province or None, history_years=args.history_years, source_ids=args.source_ids,
    )
    sources, errors = load_enabled_sources()
    sources = select_sources(sources, options)
    if not sources:
        parser.error("没有匹配的已启用来源")
    try:
        lease = RunLease().acquire()
    except CollectorBusyError as exc:
        parser.exit(2, f"{exc}\n")
    try:
        Base.metadata.create_all(engine)
        ensure_missing_columns(engine)
        backfill_reference_metadata(engine)
        with Session(engine, expire_on_commit=False) as db:
            run = execute(db, sources, errors, options, trigger="cli")
            print(json.dumps({
                "run_id": run.id, "mode": run.mode, "status": run.status,
                "new": run.new_count, "duplicates": run.duplicate_count,
                "sources": [{"id": i.source_id, "status": i.status, "new": i.new_count,
                             "warnings": i.warning_count, "error": i.error_message} for i in run.items],
            }, ensure_ascii=False, indent=2))
            return 0 if run.status == "completed" else 1
    finally:
        lease.release()


if __name__ == "__main__":
    raise SystemExit(main())
