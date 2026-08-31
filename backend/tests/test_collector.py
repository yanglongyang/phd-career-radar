"""V0.2 Collector 测试：config 解析、去重、JsonApi/HtmlList Collector、
Runner 事务隔离、API、AI Extraction bridge。"""

import json

import pytest

from app.collectors.config import SourceConfig, parse_source
from app.collectors.html_list import HtmlListCollector
from app.collectors.json_api import JsonApiCollector
from app.services.collector_dedupe import canonical_url, fingerprint, possible_duplicate_reason
from tests.conftest import JOB_PAYLOAD  # noqa: F401

# ---------- SourceConfig ----------

def test_parse_source_valid():
    src = parse_source(
        {"id": "a", "name": "A", "type": "json_api", "enabled": True, "url": "https://x/api"}
    )
    assert src.enabled is True
    assert src.request.timeout_seconds == 15.0


def test_parse_source_unknown_type():
    with pytest.raises(Exception, match="未知 collector type"):
        parse_source({"id": "a", "type": "whatever", "enabled": True, "url": "https://x"})


def test_parse_source_enabled_must_be_bool():
    with pytest.raises(Exception, match="enabled"):
        parse_source({"id": "a", "type": "json_api", "enabled": "true", "url": "https://x"})


def test_parse_source_missing_id():
    with pytest.raises(Exception, match="id"):
        parse_source({"type": "json_api", "enabled": True, "url": "https://x"})


# ---------- Dedupe ----------

def test_canonical_url_strips_utm_keeps_other_query():
    a = canonical_url("https://Example.com/jobs/123?utm_source=x&id=456#frag")
    b = canonical_url("https://example.com/jobs/123?id=456")
    assert a == b
    assert "utm" not in a
    assert "id=456" in a


def test_canonical_url_preserves_job_id_query():
    """招聘系统 query 可能是职位 ID，不得随意删除。"""
    a = canonical_url("https://x.com/jobs?id=abc")
    b = canonical_url("https://x.com/jobs?id=def")
    assert a != b


def test_canonical_url_trailing_slash_and_scheme():
    assert canonical_url("HTTP://X.com/path/") == canonical_url("http://x.com/path")
    assert canonical_url("https://x.com/a") == canonical_url("https://x.com/a?utm_campaign=y")


def test_fingerprint_deterministic():
    f1 = fingerprint("南京大学", "青年研究员招聘", "https://hr.nju.edu.cn/a/b.html")
    f2 = fingerprint("南京大学", "青年研究员招聘", "https://hr.nju.edu.cn/a/b.html")
    assert f1 == f2
    assert fingerprint("南京大学", "不同岗位", "https://x/a") != f1


def test_possible_duplicate_only_marks():
    reason = possible_duplicate_reason("青年研究员（化学生物学）招聘", "青年研究员（化学生物学）公告", url_same=False)
    assert reason is not None and "相似" in reason
    assert possible_duplicate_reason("青年研究员", "计算数学博士后", url_same=False) is None


# ---------- JsonApiCollector ----------

class _FakeFetcher:
    """可注入的 SafeFetcher 替身。"""

    def __init__(self, responses):
        self.responses = responses  # url -> (final_url, content_type, body)

    def fetch(self, url, timeout=15.0, content_types=None):
        return self.responses[url]


def _json_source(url="https://api.example.com/jobs"):
    return SourceConfig(
        id="pharma", name="药企", type="json_api", enabled=True, url=url,
        organization="某药企",
        mapping={
            "items": "data.jobs",
            "source_job_id": "id",
            "title": "title",
            "url": "apply_url",
            "date": "publish_date",
            "description": "description",
            "organization": "company",
            "location": "city",
        },
    )


def test_json_api_collector_normal(monkeypatch):
    src = _json_source()
    collector = JsonApiCollector(src)
    monkeypatch.setattr(
        collector, "_fetcher",
        _FakeFetcher({
            src.url: (
                src.url, "application/json",
                json.dumps({"data": {"jobs": [
                    {"id": "j1", "title": "研究员", "apply_url": "https://x.com/jobs/1",
                     "publish_date": "2026-08-01", "description": "做荧光探针", "company": "药企A", "city": "上海"},
                    {"id": "j2", "title": "博士后", "apply_url": "https://x.com/jobs/2"},  # 缺字段
                ]}}),
            ),
        }),
    )
    jobs = collector.collect()
    assert len(jobs) == 2
    assert jobs[0].source_job_id == "j1"
    assert jobs[0].title == "研究员"
    assert jobs[0].organization_hint == "药企A"
    assert jobs[1].description_raw is None  # 缺字段不崩溃


def test_json_api_collector_wrong_items_path(monkeypatch):
    src = _json_source()
    collector = JsonApiCollector(src)
    monkeypatch.setattr(
        collector, "_fetcher",
        _FakeFetcher({src.url: (src.url, "application/json", json.dumps({"other": []}))}),
    )
    with pytest.raises(Exception, match="items 路径"):
        collector.collect()


def test_json_api_collector_relative_url_resolved(monkeypatch):
    src = _json_source(url="https://api.example.com/v2/jobs")
    src.mapping["url"] = "relative_url"
    collector = JsonApiCollector(src)
    monkeypatch.setattr(
        collector, "_fetcher",
        _FakeFetcher({
            src.url: (src.url, "application/json",
                      json.dumps({"data": {"jobs": [
                          {"id": "a", "title": "t", "relative_url": "/jobs/9"},
                      ]}})),
        }),
    )
    jobs = collector.collect()
    assert jobs[0].source_url == "https://api.example.com/jobs/9"  # 已 resolve（P1-3）


def test_json_api_timeout_error(monkeypatch):
    src = _json_source()
    collector = JsonApiCollector(src)

    class Boom:
        def fetch(self, *a, **k):
            raise Exception("连接超时")

    monkeypatch.setattr(collector, "_fetcher", Boom())
    with pytest.raises(Exception, match="超时"):
        collector.collect()


# ---------- HtmlListCollector ----------

HTML_LIST = """
<html><body><ul class="news-list">
  <li><a href="/hr/jobs/1">青年研究员招聘公告</a><span class="date">2026-08-10</span></li>
  <li><a href="/hr/jobs/2">博士后招聘</a><span class="date">2026-08-12</span></li>
</ul></body></html>
"""
DETAIL_HTML = "<html><body><div class='article-content'><p>岗位职责：荧光探针研究。</p></div></body></html>"


def _html_source(url="https://hr.example.edu.cn/list"):
    return SourceConfig(
        id="uni", name="大学", type="html_list", enabled=True, url=url,
        organization="示例大学",
        selectors={"item": ".news-list li", "title": "a", "link": "a", "date": ".date"},
        detail={"fetch_detail": True, "content_selector": ".article-content"},
    )


def test_html_list_collector_normal(monkeypatch):
    src = _html_source()
    collector = HtmlListCollector(src)

    def fake_fetch(self, url, **kwargs):
        if url == src.url:
            return (src.url, "text/html", HTML_LIST)
        return (url, "text/html", DETAIL_HTML)

    monkeypatch.setattr(collector, "_fetcher", _FakeFetcher({}) if False else type("F", (), {"fetch": fake_fetch})())
    jobs = collector.collect()
    assert len(jobs) == 2
    assert jobs[0].title == "青年研究员招聘公告"
    assert jobs[0].source_url == "https://hr.example.edu.cn/hr/jobs/1"  # 相对 URL resolve
    assert "荧光探针" in jobs[0].description_raw  # detail 正文


def test_html_list_collector_no_detail(monkeypatch):
    src = _html_source()
    src.detail = {"fetch_detail": False}
    collector = HtmlListCollector(src)

    def fake_fetch(self, url, **kwargs):
        return (src.url, "text/html", HTML_LIST)

    monkeypatch.setattr(collector, "_fetcher", type("F", (), {"fetch": fake_fetch})())
    jobs = collector.collect()
    assert len(jobs) == 2
    assert jobs[0].description_raw is None  # 只保存列表信息


def test_html_list_collector_no_items(monkeypatch):
    src = _html_source()
    collector = HtmlListCollector(src)

    def fake_fetch(self, url, **kwargs):
        return (src.url, "text/html", "<html><body><p>nothing</p></body></html>")

    monkeypatch.setattr(collector, "_fetcher", type("F", (), {"fetch": fake_fetch})())
    assert collector.collect() == []


def test_html_list_detail_failure_does_not_kill_source(monkeypatch):
    """某条 detail 失败不应让整个 source 全部丢失。"""
    src = _html_source()
    collector = HtmlListCollector(src)
    calls = {"n": 0}

    def fake_fetch(self, url, **kwargs):
        if url == src.url:
            return (src.url, "text/html", HTML_LIST)
        calls["n"] += 1
        if calls["n"] == 1:
            raise Exception("detail 超时")
        return (url, "text/html", DETAIL_HTML)

    monkeypatch.setattr(collector, "_fetcher", type("F", (), {"fetch": fake_fetch})())
    jobs = collector.collect()
    assert len(jobs) == 2
    assert jobs[0].description_raw is None  # 失败条目跳过
    assert jobs[1].description_raw is not None  # 后续条目继续


# ---------- Runner 事务隔离（真实 DB） ----------

def _fake_collector(monkeypatch, results_by_source, fail_source=None):
    """把 runner 使用的 build_collector 替换为返回固定 RawJob 的假 collector。"""
    from app.collectors.base import JobCollector
    from app.services import collector_runner

    class FakeCollector(JobCollector):
        def __init__(self, source):
            self.source = source

        def collect(self):
            if self.source.id == fail_source:
                raise Exception("模拟抓取失败: HTTP 403")
            return results_by_source.get(self.source.id, [])

    monkeypatch.setattr(collector_runner.collectors_registry, "build_collector", FakeCollector)


def _src(source_id, org="测试大学"):
    return SourceConfig(
        id=source_id, name=f"来源{source_id}", type="json_api", enabled=True,
        url=f"https://x.com/{source_id}", organization=org,
        mapping={"items": "items", "source_job_id": "id", "title": "title", "url": "url"},
    )


def test_runner_transaction_isolation(client, db_session, monkeypatch):
    """Source A success → B fail → C success：A/C 数据真实落库，B 标记 failed。"""
    from app.models import DiscoveredJob
    from app.services.collector_runner import run_collectors

    def mk(source_id, title, url):
        from app.collectors.base import RawJob

        return RawJob(
            source_id=source_id, source_name=f"来源{source_id}", title=title,
            source_job_id=f"{source_id}-1", source_url=url, organization_hint="测试大学",
        )

    results = {
        "A": [mk("A", "岗位A", "https://a.com/jobs/1")],
        "C": [mk("C", "岗位C", "https://c.com/jobs/1")],
    }
    _fake_collector(monkeypatch, results, fail_source="B")
    sources = [_src("A"), _src("B"), _src("C")]

    run = run_collectors(db_session, sources)
    db_session.commit()
    db_session.expire_all()

    # A/C 数据存在
    assert db_session.query(DiscoveredJob).filter_by(source_id="A").count() == 1
    assert db_session.query(DiscoveredJob).filter_by(source_id="C").count() == 1
    assert db_session.query(DiscoveredJob).filter_by(source_id="B").count() == 0
    # B 标记 failed，A/C 标记 success
    item_status = {i.source_id: i.status for i in run.items}
    assert item_status == {"A": "success", "B": "failed", "C": "success"}
    assert run.failed_source_count == 1
    assert run.status == "partial_failure"
    assert "403" in run.items[1].error_message


def test_runner_second_run_dedupes_and_updates_last_seen(client, db_session, monkeypatch):
    """第二次运行：相同 source_job_id 不重建，last_seen 更新、discovered_at 不变。"""
    from app.models import DiscoveredJob
    from app.services.collector_runner import run_collectors

    def mk(title, url, source_job_id):
        from app.collectors.base import RawJob

        return RawJob(
            source_id="A", source_name="来源A", title=title,
            source_job_id=source_job_id, source_url=url, organization_hint="测试大学",
        )

    _fake_collector(monkeypatch, {"A": [mk("岗位A", "https://a.com/jobs/1", "a1")]})
    sources = [_src("A")]

    run1 = run_collectors(db_session, sources)
    db_session.commit()
    row = db_session.query(DiscoveredJob).one()
    first_seen = row.discovered_at
    first_run = row.first_run_id

    import time

    time.sleep(0.05)
    run2 = run_collectors(db_session, sources)
    db_session.commit()
    db_session.expire_all()

    assert db_session.query(DiscoveredJob).count() == 1  # 不重建
    row2 = db_session.query(DiscoveredJob).one()
    assert row2.discovered_at == first_seen  # first_seen 不变
    assert row2.last_seen_at > first_seen  # last_seen 更新
    assert row2.first_run_id == first_run
    assert row2.last_run_id == run2.id
    assert run1.duplicate_count == 0 and run2.duplicate_count == 1


def test_runner_possible_duplicate_marks_not_merges(client, db_session, monkeypatch):
    """同单位 + 标题高度相似 + URL 不同 → possible_duplicate 标记，不合并。"""
    from app.models import DiscoveredJob
    from app.services.collector_runner import run_collectors

    def mk(title, url, job_id):
        from app.collectors.base import RawJob

        return RawJob(
            source_id="A", source_name="来源A", title=title,
            source_job_id=job_id, source_url=url, organization_hint="测试大学",
        )

    _fake_collector(
        monkeypatch,
        {"A": [mk("青年研究员（化学生物学）招聘", "https://a.com/jobs/1", "x1"),
               mk("青年研究员（化学生物学）公告", "https://a.com/jobs/2", "x2")]},
    )
    run = run_collectors(db_session, [_src("A")])
    db_session.commit()

    rows = db_session.query(DiscoveredJob).order_by(DiscoveredJob.id).all()
    assert len(rows) == 2  # 不自动合并
    second = rows[1]
    assert second.status == "possible_duplicate"
    assert second.possible_duplicate_of_id == rows[0].id
    assert "相似" in (second.duplicate_reason or "")
    assert run.possible_duplicate_count == 1


def test_runner_keyword_filter(client, db_session, monkeypatch):
    """关键字过滤：命中排除 → 不入库；filtered_count 保留。"""
    from app.models import DiscoveredJob
    from app.services.collector_runner import run_collectors

    def mk(title, url, job_id):
        from app.collectors.base import RawJob

        return RawJob(
            source_id="A", source_name="来源A", title=title,
            source_job_id=job_id, source_url=url, organization_hint="测试大学",
        )

    _fake_collector(
        monkeypatch,
        {"A": [mk("有机化学教师招聘", "https://a.com/jobs/1", "k1"),
               mk("辅导员招聘", "https://a.com/jobs/2", "k2")]},
    )
    src = _src("A")
    src.filters = {"include_keywords": ["化学"], "exclude_keywords": ["辅导员"]}
    run = run_collectors(db_session, [src])
    db_session.commit()

    rows = db_session.query(DiscoveredJob).all()
    assert len(rows) == 1
    assert rows[0].title_raw == "有机化学教师招聘"
    assert run.filtered_count == 1


# ---------- API ----------

def test_collector_api_run_end_to_end(client, monkeypatch):
    """POST /api/collectors/run：source 级状态、Inbox 出现、二次运行去重。"""
    from app.collectors.base import RawJob
    from app.services import collector_runner

    def fake_build(source):
        class Fake(collector_runner.collectors_registry.JobCollector):
            def __init__(self, source):
                self.source = source

            def collect(self):
                if source.id == "bad":
                    raise Exception("HTTP 403")
                return [
                    RawJob(source_id=source.id, source_name=source.name,
                           title=f"{source.id}岗位", source_job_id=f"{source.id}-1",
                           source_url=f"https://x.com/{source.id}/jobs/1",
                           organization_hint=source.organization),
                ]

        return Fake(source)

    monkeypatch.setattr(collector_runner.collectors_registry, "build_collector", fake_build)
    # 用 monkeypatch 覆盖 load_enabled_sources
    from app.api.routes import collectors as collectors_routes

    srcs = [_src("A"), _src("B", org="测试大学2"), _src("bad", org="测试大学3")]
    monkeypatch.setattr(collectors_routes, "load_enabled_sources", lambda: (srcs, []))

    resp = client.post("/api/collectors/run")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "partial_failure"
    statuses = {i["source_id"]: i["status"] for i in data["items"]}
    assert statuses == {"A": "success", "B": "success", "bad": "failed"}
    assert data["new_count"] == 2
    assert data["failed_source_count"] == 1

    # Inbox 出现
    inbox = client.get("/api/discovered-jobs").json()
    assert inbox["total"] == 2

    # 二次运行去重
    resp2 = client.post("/api/collectors/run")
    data2 = resp2.json()
    assert data2["duplicate_count"] == 2
    inbox2 = client.get("/api/discovered-jobs").json()
    assert inbox2["total"] == 2  # 不重建


def test_discovered_jobs_patch_and_filter(client, db_session):
    from app.models import DiscoveredJob

    db_session.add_all(
        [
            DiscoveredJob(source_id="A", source_name="A", title_raw="岗位1",
                          source_url="https://x.com/1", organization_hint="大学1"),
            DiscoveredJob(source_id="B", source_name="B", title_raw="岗位2",
                          source_url="https://x.com/2", organization_hint="大学2",
                          status="possible_duplicate"),
        ]
    )
    db_session.commit()

    resp = client.patch("/api/discovered-jobs/1", json={"status": "ignored"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"

    data = client.get("/api/discovered-jobs", params={"status": "possible_duplicate"}).json()
    assert data["total"] == 1

    data = client.get("/api/discovered-jobs", params={"organization": "大学1"}).json()
    assert data["total"] == 1

    data = client.get("/api/discovered-jobs", params={"q": "岗位2"}).json()
    assert data["total"] == 1

    assert client.patch("/api/discovered-jobs/1", json={"status": "bogus"}).status_code == 422


def test_discovered_extract_bridge_uses_existing_extraction(client, monkeypatch, db_session):
    """DiscoveredJob → 现有 AI Extraction：返回 preview、状态推进 reviewing、不创建 Job。"""
    from app.ai.provider import LLMProvider
    from app.ai.schemas import JobExtractionOut
    from app.api.deps import get_ai_provider
    from app.models import DiscoveredJob, Job

    db_session.add(
        DiscoveredJob(source_id="A", source_name="A", title_raw="青年研究员",
                      source_url="https://x.com/1", organization_hint="大学1",
                      description_raw=(
                          "某某大学化学学院面向海内外公开招聘青年研究员。申请人应具有"
                          "有机化学或化学生物学博士学位，研究方向为荧光探针。"
                          "学校提供启动经费 50 万元，年薪 30-45 万。"
                      ))
    )
    db_session.commit()

    class Fake(LLMProvider):
        name = "fake"
        model = "m"

        def extract_job(self, jd_text):
            return JobExtractionOut.model_validate(
                {"title": "青年研究员", "organization": "大学1", "unknowns": []}
            ), "job_extraction_v1"

        def evaluate_job(self, context):
            raise NotImplementedError

        def summarize_reputation(self, context):
            raise NotImplementedError

    client.app.dependency_overrides[get_ai_provider] = lambda: Fake()
    try:
        resp = client.post("/api/discovered-jobs/1/extract")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["extraction"]["title"] == "青年研究员"
        assert data["prompt_version"] == "job_extraction_v1"
        # 状态推进 reviewing；不创建正式 Job
        assert client.get("/api/discovered-jobs/1").json()["status"] == "reviewing"
        assert db_session.query(Job).count() == 0
    finally:
        client.app.dependency_overrides.pop(get_ai_provider, None)


def test_discovered_extract_requires_ai(client, db_session):
    from app.models import DiscoveredJob

    db_session.add(
        DiscoveredJob(source_id="A", source_name="A", title_raw="t",
                      source_url="https://x.com/1", description_raw="正文足够长可以解析的招聘公告内容")
    )
    db_session.commit()
    assert client.post("/api/discovered-jobs/1/extract").status_code == 503


def test_collector_sources_endpoint(client, monkeypatch):
    from app.api.routes import collectors as collectors_routes

    monkeypatch.setattr(
        collectors_routes, "load_sources",
        lambda: ([
            _src("A"),
            SourceConfig(id="B", name="B", type="json_api", enabled=False, url="https://x.com/b"),
        ], []),
    )
    data = client.get("/api/collectors/sources").json()
    assert data["sources"][0]["enabled"] is True
    assert data["sources"][1]["enabled"] is False
# ---------- V0.2.1 Final Collector Integrity ----------

def test_load_sources_isolates_config_errors(monkeypatch, tmp_path):
    """P0-1：单个 source 配置错误不阻塞其他 source；duplicate id 报错。"""
    import yaml as _yaml

    from app.collectors import config as collector_config

    monkeypatch.setattr(collector_config, "CONFIG_DIR", tmp_path)
    (tmp_path / "sources.yaml").write_text(_yaml.safe_dump({
        "schema_version": 2,
        "collectors": [
            {"id": "A", "name": "A", "type": "json_api", "enabled": True, "url": "https://a.com"},
            {"id": "B", "name": "B", "type": "html_list", "enabled": True, "url": "https://b.com",
             "selectors": {"item": "li"}},
            {"id": "A", "name": "重复A", "type": "json_api", "enabled": True, "url": "https://a2.com"},
            {"id": "C", "name": "C", "type": "json_api", "enabled": "true", "url": "https://c.com"},
        ],
    }, allow_unicode=True), encoding="utf-8")

    valid, errors = collector_config.load_sources()
    assert [s.id for s in valid] == ["A", "B"]
    assert len(errors) == 2
    assert any("重复" in e["error"] for e in errors)
    assert any("enabled" in e["error"] for e in errors)


def test_runner_isolates_config_errors_in_run(client, db_session, monkeypatch):
    """P0-1 端到端：valid A / invalid B / valid C → A/C 成功落库、B failed item。"""
    from app.collectors.base import RawJob
    from app.collectors.config import SourceConfig
    from app.models import DiscoveredJob
    from app.services import collector_runner

    def fake_build(source):
        class Fake(collector_runner.collectors_registry.JobCollector):
            def __init__(self, source):
                self.source = source

            def collect(self):
                return [RawJob(source_id=source.id, source_name=source.name,
                               title=f"{source.id}岗位", source_job_id=f"{source.id}-1",
                               source_url=f"https://x.com/{source.id}/jobs/1",
                               organization_hint="大学")]

        return Fake(source)

    monkeypatch.setattr(collector_runner.collectors_registry, "build_collector", fake_build)
    sources = [
        SourceConfig(id="A", name="A", type="json_api", enabled=True, url="https://a.com",
                     organization="大学", mapping={"items": "items"}),
        SourceConfig(id="C", name="C", type="json_api", enabled=True, url="https://c.com",
                     organization="大学", mapping={"items": "items"}),
    ]
    config_errors = [{"source_id": "B", "name": "B", "error": "未知 collector type: x"}]

    run = collector_runner.run_collectors(db_session, sources, config_errors=config_errors)
    db_session.commit()
    db_session.expire_all()

    statuses = {i.source_id: i.status for i in run.items}
    assert statuses == {"A": "success", "B": "failed", "C": "success"}
    assert run.failed_source_count == 1
    assert run.source_count == 3
    assert run.completed_source_count == 3  # P1-4：结束即完成（success+failed）
    assert db_session.query(DiscoveredJob).filter_by(source_id="A").count() == 1
    assert db_session.query(DiscoveredJob).filter_by(source_id="C").count() == 1
    assert run.status == "partial_failure"


def test_possible_duplicate_requires_known_org(client, db_session, monkeypatch):
    """P1-5：单位未知（org 皆空）不执行基于组织的 possible 判定。"""
    from app.collectors.base import RawJob
    from app.collectors.config import SourceConfig
    from app.models import DiscoveredJob
    from app.services import collector_runner

    def fake_build(source):
        class Fake(collector_runner.collectors_registry.JobCollector):
            def __init__(self, source):
                self.source = source

            def collect(self):
                return [
                    RawJob(source_id="A", source_name="A", title="青年研究员招聘",
                           source_job_id="x1", source_url="https://a.com/1"),
                    RawJob(source_id="A", source_name="A", title="青年研究员公告",
                           source_job_id="x2", source_url="https://a.com/2"),
                ]

        return Fake(source)

    monkeypatch.setattr(collector_runner.collectors_registry, "build_collector", fake_build)
    src = SourceConfig(id="A", name="A", type="json_api", enabled=True, url="https://a.com",
                       organization=None, mapping={"items": "items"})  # aggregator：org 为空
    run = collector_runner.run_collectors(db_session, [src])
    db_session.commit()

    rows = db_session.query(DiscoveredJob).all()
    assert len(rows) == 2
    assert all(r.status == "new" for r in rows)  # 不因 org=NULL 互相误标
    assert run.possible_duplicate_count == 0


def test_extract_bridge_preserves_provenance(client, monkeypatch, db_session):
    """P0-2A：extract bridge 保留 source_type=url / source_url=原始招聘 URL。"""
    from app.ai.provider import LLMProvider
    from app.ai.schemas import JobExtractionOut
    from app.api.deps import get_ai_provider
    from app.models import DiscoveredJob

    db_session.add(
        DiscoveredJob(source_id="A", source_name="A", title_raw="青年研究员",
                      source_url="https://hr.example.edu.cn/jobs/123",
                      organization_hint="大学1",
                      description_raw="某某大学面向海内外公开招聘青年研究员。申请人应具有有机化学博士学位，研究方向为荧光探针。提供启动经费。")
    )
    db_session.commit()

    class Fake(LLMProvider):
        name = "fake"
        model = "m"

        def extract_job(self, jd_text):
            return JobExtractionOut.model_validate({"title": "青年研究员"}), "job_extraction_v1"

        def evaluate_job(self, context):
            raise NotImplementedError

        def summarize_reputation(self, context):
            raise NotImplementedError

    client.app.dependency_overrides[get_ai_provider] = lambda: Fake()
    try:
        resp = client.post("/api/discovered-jobs/1/extract")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_type"] == "url"
        assert data["source_url"] == "https://hr.example.edu.cn/jobs/123"  # 原始 URL 保留
        assert data["prompt_version"] == "job_extraction_v1"
    finally:
        client.app.dependency_overrides.pop(get_ai_provider, None)


def test_link_imported_job_end_to_end(client, db_session):
    """P0-2B：Save 正式 Job 后 link-imported-job 幂等回写 imported + imported_job_id。"""
    from app.models import DiscoveredJob, Job

    db_session.add(
        DiscoveredJob(source_id="A", source_name="A", title_raw="青年研究员",
                      source_url="https://x.com/1", organization_hint="大学1",
                      description_raw="招聘公告正文足够长的内容，用于测试。")
    )
    db_session.commit()
    job = Job(title="青年研究员", fingerprint="f", description_raw="x")
    db_session.add(job)
    db_session.commit()

    resp = client.post("/api/discovered-jobs/1/link-imported-job", json={"job_id": job.id})
    assert resp.status_code == 200
    assert resp.json()["status"] == "imported"
    assert resp.json()["imported_job_id"] == job.id

    # 幂等：再次调用结果一致
    resp2 = client.post("/api/discovered-jobs/1/link-imported-job", json={"job_id": job.id})
    assert resp2.status_code == 200
    assert resp2.json()["imported_job_id"] == job.id

    # 普通 PATCH 不能伪造 imported
    assert client.patch("/api/discovered-jobs/1", json={"status": "imported"}).status_code == 422
    # 不存在的正式岗位 → 404
    assert client.post("/api/discovered-jobs/1/link-imported-job", json={"job_id": 99999}).status_code == 404


def test_ensure_sources_schema_migrates_legacy(monkeypatch, tmp_path):
    """P1-7：legacy 空 sources.yaml → 迁移到 bundled 默认（备份 + schema_version 2）。"""
    import yaml as _yaml

    from app.collectors import config as collector_config
    from app.core import config as core_config

    user_dir = tmp_path / "user"
    bundle_dir = tmp_path / "bundle"
    (user_dir / "config").mkdir(parents=True)
    (bundle_dir / "config").mkdir(parents=True)
    (user_dir / "config" / "sources.yaml").write_text("collectors: []\n", encoding="utf-8")
    (bundle_dir / "config" / "sources.yaml").write_text(
        _yaml.safe_dump({"schema_version": 2, "collectors": [
            {"id": "nju", "name": "NJU", "type": "html_list", "enabled": True,
             "url": "https://x.com"}]}, allow_unicode=True),
        encoding="utf-8",
    )

    monkeypatch.setattr(collector_config, "CONFIG_DIR", user_dir / "config")
    monkeypatch.setattr(core_config, "RESOURCE_ROOT", bundle_dir)

    result = collector_config.ensure_sources_schema()
    assert result["migrated"] is True
    migrated = _yaml.safe_load((user_dir / "config" / "sources.yaml").read_text(encoding="utf-8"))
    assert migrated["schema_version"] == 2
    assert migrated["collectors"][0]["id"] == "nju"
    assert (user_dir / "config" / "sources.yaml.legacy.bak").exists()

    # 已有版本（用户主动清空）尊重，不覆盖
    (user_dir / "config" / "sources.yaml").write_text(
        _yaml.safe_dump({"schema_version": 2, "collectors": []}), encoding="utf-8"
    )
    result2 = collector_config.ensure_sources_schema()
    assert result2["migrated"] is False
    assert _yaml.safe_load((user_dir / "config" / "sources.yaml").read_text(encoding="utf-8"))["collectors"] == []
# ---------- 日期解析与过期过滤（V0.2.2） ----------

def test_parse_date_from_text_formats():
    from datetime import date

    from app.collectors.config import parse_date_from_text

    assert parse_date_from_text("2026.08.24") == date(2026, 8, 24)
    assert parse_date_from_text("2023-07-05") == date(2023, 7, 5)
    assert parse_date_from_text("发布日期：2016-11-29") == date(2016, 11, 29)
    assert parse_date_from_text("2025年9月8日") == date(2025, 9, 8)
    # 无完整日期（月日缺失）不误匹配
    assert parse_date_from_text("2025年专任教师招聘启事") is None
    assert parse_date_from_text("华中科技大学专任教师招聘启事2024-12-20") == date(2024, 12, 20)
    assert parse_date_from_text("") is None
    assert parse_date_from_text(None) is None
    # 非法日期（2月30日）不抛异常
    assert parse_date_from_text("2023-02-30") is None


def test_parse_source_max_age_days_validation():
    src = parse_source({"id": "a", "type": "json_api", "enabled": True,
                        "url": "https://x", "max_age_days": 365})
    assert src.max_age_days == 365
    for bad in (0, -1, "365", 3.5, True):
        with pytest.raises(Exception, match="max_age_days"):
            parse_source({"id": "a", "type": "json_api", "enabled": True,
                          "url": "https://x", "max_age_days": bad})


def test_html_list_collector_pku_title_attr_date(monkeypatch):
    """北大：真实公告在 li dl dd，日期在 a 的 title 属性里（发布日期：YYYY-MM-DD）。"""
    html = """<html><body><ul class="mode2Ul">
      <li><div class="mode2container"><div class="title2"><a class="tit" href="rczp/jxky/index.htm">教学科研</a></div>
        <dl><dd><a class="gp-f16" href="rczp/jxky/abc.htm" title="2026年北京大学教学科研岗位招聘启事 发布日期：2026-02-14 ">2026年北京大学教学科研岗位招聘启事</a></dd>
        <dd><a class="gp-f16" href="rczp/bsh/def.htm" title="博士后招聘信息请点此查看 发布日期：2016-11-29">博士后招聘信息请点此查看</a></dd></dl>
      </div></li></ul></body></html>"""
    src = SourceConfig(
        id="pku", name="北大", type="html_list", enabled=True, url="https://hr.pku.edu.cn/",
        organization="北京大学",
        selectors={
            "item": "ul.mode2Ul li dl dd", "title": "a", "link": "a",
            "date": "a", "date_attr": "title",
            "title_require_words": ["招聘", "博士后"],
        },
    )
    collector = HtmlListCollector(src)

    def fake_fetch(self, url, **kwargs):
        return (src.url, "text/html", html)

    monkeypatch.setattr(collector, "_fetcher", type("F", (), {"fetch": fake_fetch})())
    jobs = collector.collect()
    assert len(jobs) == 2
    assert jobs[0].title == "2026年北京大学教学科研岗位招聘启事"
    assert jobs[0].published_at_raw == "2026-02-14"
    assert jobs[1].published_at_raw == "2016-11-29"


def test_html_list_collector_hust_row_scan_date(monkeypatch):
    """华科：日期嵌在 li 文本末尾，无 date 选择器时扫描整行文本。"""
    html = """<html><body><ul class="ss">
      <li><a href="rczp/zrjszp/1.htm">华中科技大学专任教师招聘启事</a>2023-07-05</li>
      <li><a href="rczp/zrjszp/2.htm">华中科技大学同济医学院法医学系教师招聘启事</a>2026-01-29</li>
    </ul></body></html>"""
    src = SourceConfig(
        id="hust", name="华科", type="html_list", enabled=True,
        url="https://hr.hust.edu.cn/rczp/zrjszp.htm", organization="华中科技大学",
        selectors={"item": "ul.ss li", "title": "a", "link": "a", "date": "",
                   "title_require_words": ["招聘", "教师"]},
    )
    collector = HtmlListCollector(src)

    def fake_fetch(self, url, **kwargs):
        return (src.url, "text/html", html)

    monkeypatch.setattr(collector, "_fetcher", type("F", (), {"fetch": fake_fetch})())
    jobs = collector.collect()
    assert len(jobs) == 2
    assert jobs[0].published_at_raw == "2023-07-05"
    assert jobs[1].published_at_raw == "2026-01-29"


def test_runner_recency_filter_skips_old_jobs(client, db_session, monkeypatch):
    """max_age_days=365：2016/2023 的旧岗位跳过（recency_skipped），近期岗位正常入库。"""
    from app.models import DiscoveredJob
    from app.services.collector_runner import run_collectors

    def mk(title, url, job_id, date_raw):
        from app.collectors.base import RawJob

        return RawJob(
            source_id="A", source_name="来源A", title=title,
            source_job_id=job_id, source_url=url, organization_hint="测试大学",
            published_at_raw=date_raw,
        )

    _fake_collector(
        monkeypatch,
        {"A": [mk("有机化学教师招聘", "https://a.com/jobs/1", "k1", "2026-08-10"),
               mk("博士后招聘", "https://a.com/jobs/2", "k2", "2016-11-29"),
               mk("研究员招聘", "https://a.com/jobs/3", "k3", "2023-07-05")]},
    )
    src = _src("A")
    src.max_age_days = 365
    run = run_collectors(db_session, [src])
    db_session.commit()

    rows = db_session.query(DiscoveredJob).all()
    assert len(rows) == 1
    assert rows[0].title_raw == "有机化学教师招聘"
    assert run.recency_skipped_count == 2
    assert run.filtered_count == 0
    item = run.items[0]
    assert item.recency_skipped_count == 2
    assert item.new_count == 1
