"""Historical-reference semantics, enrichment, upgrades and scheduler regressions."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.collectors.base import RawJob
from app.collectors.config import SourceConfig
from app.models import CollectorRun, DiscoveredJob
from app.schemas.collector import CollectorRunRequest
from app.services import announcement_reference as reference
from app.services import collector_runner as runner
from app.services import collector_tasks as tasks


@pytest.fixture(autouse=True)
def fixed_year_and_lock(monkeypatch, tmp_path):
    monkeypatch.setattr(reference, "current_year", lambda: 2026)
    monkeypatch.setattr(runner, "current_year", lambda: 2026)
    monkeypatch.setattr(runner, "_now", lambda: datetime(2026, 10, 30, tzinfo=UTC))
    monkeypatch.setattr(tasks, "LOCK_PATH", tmp_path / "collector.lock")


def source(source_id="s", **kwargs):
    return SourceConfig(
        id=source_id, name="山西高校", type="html_list", enabled=True,
        organization="测试大学", province="山西", history={"enabled": True}, **kwargs,
    )


def raw(year=2025, **kwargs):
    return RawJob(
        source_id="s", source_name="山西高校", title=f"测试大学{year}年博士招聘",
        published_at_raw=f"{year}-03-01", source_url=f"https://example.edu.cn/{year}.htm", **kwargs,
    )


def fake_collectors(monkeypatch, rows, warnings=None):
    class FakeCollector:
        def __init__(self, config):
            self.source = config
            self.warnings = warnings or []

        def collect(self):
            return rows.get(self.source.id, [])

    monkeypatch.setattr(runner.collectors_registry, "build_collector", FakeCollector)


@pytest.mark.parametrize(("title", "published", "expected", "origin"), [
    ("2027年博士招聘公告", "2026-10-20", 2027, "title"),
    ("26届硕士管培生", "2025-09-10", 2026, "title"),
    ("博士招聘公告", "2025年3月2日", 2025, "published_at"),
    ("博士招聘公告", None, None, "unknown"),
    ("2024-2025年度招聘", "2025-03-02", None, "ambiguous_title"),
    ("2024年招聘（2026年转载）", "2026-03-02", None, "ambiguous_title"),
])
def test_year_uses_notice_not_crawl_date(title, published, expected, origin):
    assert reference.announcement_year(title, published) == (expected, origin)


def test_year_status_changes_without_rewriting_rows():
    assert reference.reference_status(2025, 2026) == "historical"
    assert reference.reference_status(2026, 2026) == "current_year"
    assert reference.reference_status(2027, 2026) == "upcoming"
    assert reference.reference_status(None, 2026) == "unknown"
    assert reference.reference_status(2026, 2027) == "historical"


def test_excerpt_preserves_conditions_and_no_salary_inference():
    text = "岗位要求：生物学博士。待遇：符合A档条件者安家费50万元，分5年发放。服务期8年，离职须返还。"
    value = reference.excerpt(text, reference.BENEFIT_WORDS)
    assert "符合A档条件者安家费50万元，分5年发放" in value
    assert "服务期8年，离职须返还" in value
    assert reference.excerpt("欢迎报名，联系人李老师。", reference.BENEFIT_WORDS) is None


def test_history_bypasses_recency_but_limits_years(db_session, monkeypatch):
    fake_collectors(monkeypatch, {"s": [raw(y) for y in (2022, 2023, 2024, 2025, 2026, 2027)]})
    result = runner.run_collectors(db_session, [source(max_age_days=365)], mode="history", history_years=3)
    db_session.commit()
    assert {r.announcement_year for r in db_session.scalars(select(DiscoveredJob))} == {2023, 2024, 2025}
    assert result.recency_skipped_count == 3
    assert result.new_count == 3
    assert result.possible_duplicate_count == 0
    assert result.mode == "history" and result.history_years == 3


def test_recent_still_obeys_recency(db_session, monkeypatch):
    fake_collectors(monkeypatch, {"s": [raw(2024), raw(2026)]})
    result = runner.run_collectors(db_session, [source(max_age_days=365)])
    assert result.new_count == 1 and result.recency_skipped_count == 1


def test_missing_year_is_explicit_not_current(db_session, monkeypatch):
    job = RawJob(source_id="s", source_name="s", title="长期招聘博士", source_url="https://example.com/a")
    fake_collectors(monkeypatch, {"s": [job]})
    runner.run_collectors(db_session, [source()], mode="history")
    saved = db_session.scalar(select(DiscoveredJob))
    assert saved.announcement_year is None
    assert reference.reference_status(saved.announcement_year) == "unknown"


def test_official_procedure_words_in_body_do_not_discard_notice(db_session, monkeypatch):
    text = "岗位要求：生物学博士。面试通过后体检、公示。待遇：年薪30万元，服务期5年。"
    fake_collectors(monkeypatch, {"s": [raw(description_raw=text)]})
    src = source(filters={"include_keywords": ["博士"], "exclude_keywords": ["面试", "公示", "体检"]})
    result = runner.run_collectors(db_session, [src], mode="history")
    assert result.new_count == 1
    saved = db_session.scalar(select(DiscoveredJob))
    assert "博士" in saved.requirements_summary
    assert "30万元" in saved.benefits_summary


def test_followup_notice_title_is_filtered(db_session, monkeypatch):
    job = raw()
    job.title = "2025年博士招聘拟聘人员公示"
    fake_collectors(monkeypatch, {"s": [job]})
    result = runner.run_collectors(db_session, [source(filters={"exclude_title_keywords": ["拟聘", "公示"]})])
    assert result.filtered_count == 1 and result.new_count == 0


def test_detail_enrichment_is_idempotent_and_retains_source_audit(db_session, monkeypatch):
    fake_collectors(monkeypatch, {"s": [raw()]})
    runner.run_collectors(db_session, [source()], mode="history")
    original = db_session.scalar(select(DiscoveredJob))
    original.status = "ignored"
    first_run = original.first_run_id
    job = raw(description_raw="要求生物学博士。年薪20万元，安家费30万元。", raw_payload={
        "detail_status": "complete", "attachments": [{"url": "https://example.edu.cn/jobs.pdf", "title": "岗位表"}],
    })
    fake_collectors(monkeypatch, {"s": [job]})
    result = runner.run_collectors(db_session, [source()], mode="history")
    assert result.duplicate_count == 1 and result.new_count == 0
    assert original.first_run_id == first_run and original.status == "ignored"
    assert original.announcement_year == 2025 and original.province == "山西"
    assert original.raw_payload_json["attachments"] and "安家费30万元" in original.benefits_summary
    job.description_raw = None
    job.raw_payload = {"detail_status": "failed", "detail_error": "HTTP 503"}
    runner.run_collectors(db_session, [source()], mode="history")
    assert original.description_raw and original.raw_payload_json["detail_status"] == "complete"
    assert original.raw_payload_json["last_fetch_error"] == "HTTP 503"


def test_partial_detail_failure_is_visible_without_losing_good_rows(db_session, monkeypatch):
    fake_collectors(monkeypatch, {"s": [raw()]}, warnings=["某详情 HTTP 503"])
    result = runner.run_collectors(db_session, [source()], mode="history")
    assert result.status == "partial_failure"
    assert result.items[0].status == "partial_failure" and result.items[0].warning_count == 1
    assert result.new_count == 1 and "503" in result.items[0].error_message


def test_reused_url_keeps_annual_salary_snapshots_separate(db_session, monkeypatch):
    old = raw(2025, description_raw="年薪20万元。", source_job_id="recruit", raw_payload={"detail_status": "complete"})
    new = raw(2026, description_raw="年薪50万元。", source_job_id="recruit", raw_payload={"detail_status": "complete"})
    new.source_url = old.source_url
    fake_collectors(monkeypatch, {"s": [old]})
    runner.run_collectors(db_session, [source()])
    first = db_session.scalar(select(DiscoveredJob))
    first.status = "ignored"
    fake_collectors(monkeypatch, {"s": [new]})
    second_run = runner.run_collectors(db_session, [source()])
    assert second_run.new_count == 1
    rows = db_session.scalars(select(DiscoveredJob).order_by(DiscoveredJob.announcement_year)).all()
    assert len(rows) == 2
    assert rows[0].announcement_year == 2025 and rows[0].benefits_summary == "年薪20万元。"
    assert rows[0].title_raw == old.title and rows[0].status == "ignored"
    assert rows[1].announcement_year == 2026 and rows[1].benefits_summary == "年薪50万元。"
    assert rows[1].title_raw == new.title and rows[1].status == "new"
    assert rows[0].url_identity == rows[1].url_identity
    # Refetch both years repeatedly without creating a third record or moving
    # the new salary into the archived annual notice.
    fake_collectors(monkeypatch, {"s": [old, new]})
    result = runner.run_collectors(db_session, [source()])
    assert result.duplicate_count == 2 and result.new_count == 0


def test_manual_narrow_run_does_not_delay_scheduled_history(db_session):
    now = datetime(2026, 10, 30, tzinfo=UTC)
    db_session.add(CollectorRun(status="completed", mode="history", trigger="manual", province="山西",
                                history_years=1, started_at=now, finished_at=now))
    db_session.commit()
    assert tasks.is_due(db_session, "history", tasks.ScheduleConfig(enabled=True), now)


def test_interrupted_run_recovers_when_scheduler_disabled(db_session):
    db_session.add(CollectorRun(status="running", mode="history", trigger="manual", province="山西"))
    db_session.commit()
    lease = tasks.RunLease().acquire()
    try:
        tasks.recover_interrupted_runs(db_session)
    finally:
        lease.release()
    saved = db_session.scalar(select(CollectorRun))
    assert saved.status == "interrupted" and saved.finished_at is not None


def test_interrupted_scheduled_run_retries_without_waiting_a_week(db_session):
    db_session.add(CollectorRun(status="running", mode="history", trigger="scheduled",
                                province="山西", history_years=3))
    db_session.commit()
    tasks.recover_interrupted_runs(db_session)
    assert tasks.is_due(db_session, "history", tasks.ScheduleConfig(enabled=True))


def test_employer_from_configured_names_not_government_publisher(db_session, monkeypatch):
    job = raw()
    job.title = "山西白求恩医院2025年博士招聘公告"
    src = source()
    src.organization = None
    src.sector = "hospital"
    src.raw = {"organizations": ["山西白求恩医院", "山西省人民医院"]}
    fake_collectors(monkeypatch, {"s": [job]})
    runner.run_collectors(db_session, [src], mode="history")
    saved = db_session.scalar(select(DiscoveredJob))
    assert saved.organization_hint == "山西白求恩医院"


def test_old_inbox_backfill_does_not_change_review_status(db_engine, db_session):
    row = DiscoveredJob(source_id="old", source_name="old", source_url="https://example.com/2024",
                        title_raw="2024年博士招聘", description_raw="博士学位，安家费30万元。", status="ignored")
    db_session.add(row)
    db_session.commit()
    assert reference.backfill_reference_metadata(db_engine) == 1
    db_session.refresh(row)
    assert row.announcement_year == 2024 and row.status == "ignored"
    assert "30万元" in row.benefits_summary
    assert reference.backfill_reference_metadata(db_engine) == 0


def test_history_and_province_source_selection():
    regular = source()
    seeds = source("seeds")
    seeds.history["only"] = True
    elsewhere = source("elsewhere")
    elsewhere.province = "江苏"
    options = CollectorRunRequest(province="山西")
    assert tasks.select_sources([regular, seeds, elsewhere], options) == [regular]
    options.mode = "history"
    assert tasks.select_sources([regular, seeds, elsewhere], options) == [regular, seeds]
    with pytest.raises(ValueError, match="未启用"):
        tasks.select_sources([regular], CollectorRunRequest(source_ids=["missing"]))


def test_run_lock_is_exclusive_and_reusable():
    first = tasks.RunLease().acquire()
    try:
        with pytest.raises(tasks.CollectorBusyError):
            tasks.RunLease().acquire()
    finally:
        first.release()
    tasks.RunLease().acquire().release()


def test_scheduled_runs_survive_restarts_by_consulting_database(db_session):
    now = datetime(2026, 10, 30, tzinfo=UTC)
    config = tasks.ScheduleConfig(enabled=True)
    assert tasks.is_due(db_session, "recent", config, now)
    db_session.add(CollectorRun(status="completed", mode="recent", trigger="scheduled", province="山西", started_at=now,
                                finished_at=now - timedelta(hours=1)))
    db_session.commit()
    assert not tasks.is_due(db_session, "recent", config, now)
    assert tasks.is_due(db_session, "recent", config, now + timedelta(hours=12))
    assert tasks.is_due(db_session, "history", config, now)


def test_background_run_finishes_and_releases_lock(db_engine, db_session, monkeypatch):
    fake_collectors(monkeypatch, {"s": [raw()]})
    thread = tasks.start_run(db_engine, [source()], [], CollectorRunRequest(mode="history", province="山西"))
    thread.join(timeout=5)
    assert not thread.is_alive() and not tasks._run_lock.locked()
    saved = db_session.scalar(select(DiscoveredJob))
    assert saved is not None and saved.announcement_year == 2025


def test_api_filters_year_and_reference_status(client, db_session, monkeypatch):
    from app.api.routes import collectors

    monkeypatch.setattr(collectors, "current_year", lambda: 2026)
    fake_collectors(monkeypatch, {"s": [raw(y) for y in (2024, 2026, 2027)]})
    runner.run_collectors(db_session, [source()])
    db_session.commit()
    history = client.get("/api/discovered-jobs?province=山西&reference_status=historical").json()
    assert history["total"] == 1 and history["items"][0]["announcement_year"] == 2024
    assert history["items"][0]["reference_status"] == "historical"
    upcoming = client.get("/api/discovered-jobs?reference_status=upcoming").json()
    assert upcoming["total"] == 1 and upcoming["items"][0]["announcement_year"] == 2027
    assert client.get("/api/discovered-jobs?announcement_year=2026").json()["total"] == 1
    assert client.get("/api/discovered-jobs?reference_status=expired").status_code == 422


def test_async_start_validates_and_returns_quickly(client, monkeypatch):
    from app.api.routes import collectors

    received = []
    monkeypatch.setattr(collectors, "load_enabled_sources", lambda: ([source()], []))
    monkeypatch.setattr(tasks, "start_run", lambda *args, **kw: received.append(args))
    response = client.post("/api/collectors/start", json={"mode": "history", "province": "山西"})
    assert response.status_code == 202 and response.json() == {"status": "started"}
    assert received[0][3].mode == "history"
    assert client.post("/api/collectors/start", json={"history_years": 0}).status_code == 422
    assert client.post("/api/collectors/start", json={"province": "不存在"}).status_code == 422


def test_schedule_invalid_configuration_is_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(tasks, "CONFIG_DIR", tmp_path)
    (tmp_path / "collector_schedule.yaml").write_text("enabled: definitely\ninterval_hours: 0", encoding="utf8")
    status = tasks.scheduler_status()
    assert status["enabled"] is False and "配置无效" in status["last_error"]
