"""V0.2.1 Final Closure 回归测试。"""

import yaml


def test_all_sources_failed_run_status_failed(client, db_session, monkeypatch):
    """Blocker 1：全部 source 失败 → status=failed（completed=source_count）。"""
    from app.collectors.config import SourceConfig
    from app.services import collector_runner

    def fake_build(source):
        class Fake(collector_runner.collectors_registry.JobCollector):
            def __init__(self, source):
                self.source = source

            def collect(self):
                raise Exception(f"HTTP 500: {self.source.id}")

        return Fake(source)

    monkeypatch.setattr(collector_runner.collectors_registry, "build_collector", fake_build)
    sources = [
        SourceConfig(id=f"S{i}", name=f"来源{i}", type="json_api", enabled=True,
                     url=f"https://x.com/{i}", mapping={"items": "items"})
        for i in (1, 2, 3)
    ]
    run = collector_runner.run_collectors(db_session, sources)
    db_session.commit()
    assert run.completed_source_count == 3
    assert run.failed_source_count == 3
    assert run.status == "failed"  # 不是 partial_failure


def test_duplicate_id_rejected_even_if_first_fails(monkeypatch, tmp_path):
    """边角 1：同名 id 第一个配置失败，第二个也不得合法执行。"""
    from app.collectors import config as collector_config

    monkeypatch.setattr(collector_config, "CONFIG_DIR", tmp_path)
    (tmp_path / "sources.yaml").write_text(yaml.safe_dump({
        "schema_version": 2,
        "collectors": [
            {"id": "A", "name": "坏A", "type": "broken_type", "enabled": True, "url": "https://a.com"},
            {"id": "A", "name": "好A", "type": "html_list", "enabled": True, "url": "https://a2.com",
             "selectors": {"item": "li"}},
        ],
    }, allow_unicode=True), encoding="utf-8")

    valid, errors = collector_config.load_sources()
    assert valid == []  # 第二个 A 因重复被拒，即使第一个解析失败
    assert len(errors) == 2
    assert any("重复" in e["error"] for e in errors)


def test_link_imported_rejects_rebind_to_different_job(client, db_session):
    """边角 2：已链接到 Job A 后，链接 Job B → 409，不改写 provenance。"""
    from app.models import DiscoveredJob, Job

    db_session.add(
        DiscoveredJob(source_id="A", source_name="A", title_raw="青年研究员",
                      source_url="https://x.com/1", organization_hint="大学1",
                      description_raw="招聘公告正文足够长的内容，用于测试。")
    )
    db_session.commit()
    job_a = Job(title="岗位A", fingerprint="fa", description_raw="x")
    job_b = Job(title="岗位B", fingerprint="fb", description_raw="y")
    db_session.add_all([job_a, job_b])
    db_session.commit()

    assert client.post("/api/discovered-jobs/1/link-imported-job", json={"job_id": job_a.id}).status_code == 200
    resp = client.post("/api/discovered-jobs/1/link-imported-job", json={"job_id": job_b.id})
    assert resp.status_code == 409
    assert "禁止重绑" in resp.text
    assert db_session.query(DiscoveredJob).get(1).imported_job_id == job_a.id  # 未被改写
    # 同一 Job 幂等仍允许
    assert client.post("/api/discovered-jobs/1/link-imported-job", json={"job_id": job_a.id}).status_code == 200


def test_default_sources_yaml_has_schema_version():
    """Blocker 2：仓库默认 sources.yaml 必须带 schema_version: 2。"""
    from app.core.config import CONFIG_DIR

    data = yaml.safe_load((CONFIG_DIR / "sources.yaml").read_text(encoding="utf-8"))
    assert data.get("schema_version") == 2


def test_user_cleared_sources_respected_after_seed(monkeypatch, tmp_path):
    """Blocker 2 语义：bundled 默认 seed 后，用户主动清空 collectors →
    ensure_sources_schema 不再恢复默认。"""
    from app.collectors import config as collector_config
    from app.core import config as core_config

    user_dir = tmp_path / "user"
    bundle_dir = tmp_path / "bundle"
    (user_dir / "config").mkdir(parents=True)
    (bundle_dir / "config").mkdir(parents=True)
    # bundled 默认（带版本）
    (bundle_dir / "config" / "sources.yaml").write_text(
        yaml.safe_dump({"schema_version": 2, "collectors": [{"id": "nju", "type": "html_list",
                                                             "enabled": True, "url": "https://x.com"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(collector_config, "CONFIG_DIR", user_dir / "config")
    monkeypatch.setattr(core_config, "RESOURCE_ROOT", bundle_dir)

    # 模拟 seed_user_config：bundled 默认复制到用户目录（带 schema_version 2）
    import shutil

    shutil.copy2(bundle_dir / "config" / "sources.yaml", user_dir / "config" / "sources.yaml")
    assert yaml.safe_load((user_dir / "config" / "sources.yaml").read_text(encoding="utf-8"))["schema_version"] == 2

    # 用户主动清空
    (user_dir / "config" / "sources.yaml").write_text(
        yaml.safe_dump({"schema_version": 2, "collectors": []}), encoding="utf-8"
    )
    result = collector_config.ensure_sources_schema()
    assert result["migrated"] is False
    assert yaml.safe_load((user_dir / "config" / "sources.yaml").read_text(encoding="utf-8"))["collectors"] == []
