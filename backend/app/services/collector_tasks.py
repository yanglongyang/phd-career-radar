"""Local, restart-aware collection scheduling and non-blocking manual runs.

No AI calls, messaging, or application submissions. A portable file lock and a
process lock prevent concurrent manual/scheduled/CLI crawls of the same data.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import UTC, datetime, timedelta

import yaml
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.config import SourceConfig, load_enabled_sources
from app.core.config import CONFIG_DIR, DATA_DIR
from app.models import CollectorRun
from app.schemas.collector import CollectorRunRequest
from app.services import collector_runner

logger = logging.getLogger(__name__)
LOCK_PATH = DATA_DIR / "collector.lock"
_run_lock = threading.Lock()
_last_error: str | None = None


class CollectorBusyError(RuntimeError):
    pass


class ScheduleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    enabled: bool = False
    province: str | None = "山西"
    interval_hours: int = Field(default=12, ge=1, le=8760)
    history_interval_hours: int = Field(default=168, ge=1, le=8760)
    history_years: int = Field(default=3, ge=1, le=10)


def load_schedule() -> ScheduleConfig:
    path = CONFIG_DIR / "collector_schedule.yaml"
    if not path.exists():
        return ScheduleConfig()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ScheduleConfig.model_validate(data if data is not None else {})


def select_sources(sources: list[SourceConfig], options: CollectorRunRequest) -> list[SourceConfig]:
    selected = [s for s in sources if not options.province or s.province == options.province]
    if options.source_ids is not None:
        known = {s.id for s in sources}
        unknown = set(options.source_ids) - known
        if unknown:
            raise ValueError(f"来源未启用或不存在: {', '.join(sorted(unknown))}")
        selected = [s for s in selected if s.id in options.source_ids]
    if options.mode == "history":
        selected = [s for s in selected if s.history.get("enabled", False)]
    else:
        selected = [s for s in selected if not s.history.get("only", False)]
    return selected


class RunLease:
    """An OS-released lock survives neither process exit nor computer reboot."""

    def __init__(self):
        self.handle = None

    def acquire(self) -> RunLease:
        if not _run_lock.acquire(blocking=False):
            raise CollectorBusyError("已有招聘采集正在运行，请等待本次完成")
        try:
            LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.handle = LOCK_PATH.open("a+b")
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0, os.SEEK_END)
                if self.handle.tell() == 0:
                    self.handle.write(b"0")
                    self.handle.flush()
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return self
        except Exception as exc:
            if self.handle is not None:
                self.handle.close()
                self.handle = None
            _run_lock.release()
            if isinstance(exc, OSError):
                raise CollectorBusyError("另一个进程正在采集，或无法取得采集锁") from exc
            raise

    def release(self) -> None:
        if self.handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None
            _run_lock.release()


def recover_interrupted_runs(db: Session) -> None:
    """Call only while holding RunLease: no other live worker owns these runs."""
    for run in db.scalars(select(CollectorRun).where(CollectorRun.status == "running")):
        run.status = "interrupted"
        run.finished_at = datetime.now(UTC)
        for item in run.items:
            if item.status == "running":
                item.status = "failed"
                item.finished_at = run.finished_at
                item.error_message = "上次采集被中断；已完成来源的数据已保留"
        run.completed_source_count = len(run.items)
        run.failed_source_count = sum(i.status == "failed" for i in run.items)
    db.commit()


def execute(
    db: Session, sources: list[SourceConfig], errors: list[dict], options: CollectorRunRequest,
    *, trigger: str = "manual",
):
    recover_interrupted_runs(db)
    run = collector_runner.run_collectors(
        db, sources, config_errors=errors, mode=options.mode,
        history_years=options.history_years, trigger=trigger, province=options.province,
    )
    db.commit()
    return run


def start_run(
    bind, sources: list[SourceConfig], errors: list[dict], options: CollectorRunRequest,
    *, trigger: str = "manual",
) -> threading.Thread:
    lease = RunLease().acquire()

    def work():
        global _last_error
        try:
            with Session(bind, expire_on_commit=False) as db:
                execute(db, sources, errors, options, trigger=trigger)
            _last_error = None
        except Exception as exc:
            _last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            logger.exception("Recruitment collection failed")
            try:
                with Session(bind) as db:
                    recover_interrupted_runs(db)
            except Exception:
                logger.exception("Could not finalize interrupted recruitment run")
        finally:
            lease.release()

    thread = threading.Thread(target=work, name="recruitment-collector", daemon=True)
    try:
        thread.start()
    except Exception:
        lease.release()
        raise
    return thread


def scheduler_status() -> dict:
    try:
        config = load_schedule()
        error = _last_error
    except (ValueError, OSError, yaml.YAMLError) as exc:
        config = ScheduleConfig()
        error = f"自动采集配置无效: {str(exc)[:300]}"
    return {**config.model_dump(), "running": _run_lock.locked(), "last_error": error}


def is_due(db: Session, mode: str, config: ScheduleConfig, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    stmt = select(CollectorRun).where(
        CollectorRun.mode == mode, CollectorRun.province == config.province,
        CollectorRun.trigger == "scheduled",
    )
    if mode == "history":
        stmt = stmt.where(CollectorRun.history_years == config.history_years)
    # An aborted run should retry after restart, but a completed attempt with
    # blocked websites must not hammer them every minute.
    last = db.scalars(stmt.order_by(CollectorRun.id.desc()).limit(1)).first()
    if last is None or last.finished_at is None or last.status == "interrupted":
        return True
    finished = last.finished_at.replace(tzinfo=UTC) if last.finished_at.tzinfo is None else last.finished_at
    hours = config.history_interval_hours if mode == "history" else config.interval_hours
    return now - finished >= timedelta(hours=hours)


class CollectorScheduler:
    def __init__(self, bind):
        self.bind = bind
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def tick(self) -> None:
        global _last_error
        config = load_schedule()  # User edits take effect without restarting.
        if not config.enabled or _run_lock.locked():
            return
        with Session(self.bind) as db:
            for mode in ("recent", "history"):
                if not is_due(db, mode, config):
                    continue
                options = CollectorRunRequest(mode=mode, province=config.province, history_years=config.history_years)
                sources, errors = load_enabled_sources()
                sources = select_sources(sources, options)
                if not sources:
                    _last_error = "没有匹配地区且已启用的采集来源，请检查来源配置"
                    continue
                try:
                    start_run(self.bind, sources, errors, options, trigger="scheduled")
                except CollectorBusyError:
                    return
                return  # The next tick starts history after the current run.

    def start(self) -> None:
        def loop():
            global _last_error
            if self.stop_event.wait(20):
                return
            while not self.stop_event.is_set():
                try:
                    self.tick()
                except Exception as exc:
                    _last_error = f"自动采集未启动: {str(exc)[:300]}"
                    logger.exception("Recruitment scheduler error")
                self.stop_event.wait(60)

        self.thread = threading.Thread(target=loop, name="recruitment-scheduler", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
