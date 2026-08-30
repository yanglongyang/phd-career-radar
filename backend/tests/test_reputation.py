"""Phase 6：Evidence CRUD 与风评聚合（确定性统计 + AI 叙述综合）测试。"""

import pytest

from app.ai.provider import LLMProvider
from app.ai.schemas import ReputationSynthesisOut
from app.models import EvaluationEvidence
from tests.conftest import JOB_PAYLOAD


@pytest.fixture()
def sample_job_with_evidence(client):
    """岗位 + 组织级证据若干，覆盖各种 scope/stance/等级。"""
    job = client.post("/api/jobs", json=JOB_PAYLOAD).json()
    org_id = job["organization"]["id"]
    return job, org_id


def _evidence(client, org_id, **kwargs):
    base = {"claim": "启动经费到账偏慢", "category": "startup_funding_fulfillment",
            "evidence_level": "C", "source_type": "forum", "stance": "negative",
            "scope_level": "organization"}
    base.update(kwargs)
    resp = client.post(f"/api/evidence/organizations/{org_id}", json=base)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------- Evidence CRUD ----------

def test_create_job_evidence_inherits_organization(client, sample_job_with_evidence):
    job, org_id = sample_job_with_evidence
    resp = client.post(
        f"/api/evidence/jobs/{job['id']}",
        json={"claim": "公告写明聘期六年", "category": "fact", "evidence_level": "A",
              "source_type": "official", "stance": "neutral"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["job_id"] == job["id"]
    assert data["organization_id"] == org_id  # 自动继承岗位所属单位


def test_create_organization_evidence_and_list(client, sample_job_with_evidence):
    job, org_id = sample_job_with_evidence
    created = _evidence(client, org_id, independence_key="zhihu_user_a")
    listed = client.get(f"/api/evidence/organizations/{org_id}").json()
    # 组织级列表只含无 job_id 的证据
    assert all(item["job_id"] is None for item in listed)
    assert any(item["id"] == created["id"] for item in listed)


def test_patch_and_delete_evidence(client, sample_job_with_evidence):
    _, org_id = sample_job_with_evidence
    ev = _evidence(client, org_id)
    resp = client.patch(f"/api/evidence/{ev['id']}", json={"claim": "到账约 3-6 个月", "stance": "negative"})
    assert resp.status_code == 200
    assert resp.json()["claim"] == "到账约 3-6 个月"
    # evidence_level 未提供则不变
    assert resp.json()["evidence_level"] == "C"

    assert client.delete(f"/api/evidence/{ev['id']}").status_code == 204
    assert client.get(f"/api/evidence?organization_id={org_id}").json() == []


def test_delete_evidence_cleans_evaluation_links(client, sample_job_with_evidence, db_session):
    """删除证据必须同步清理 EvaluationEvidence，不留悬挂引用。"""
    from app.ai.provider import LLMProvider
    from app.ai.schemas import JobEvaluationOut as AIEvalOut
    from app.services.evaluation import evaluate_job

    job, org_id = sample_job_with_evidence
    ev = _evidence(client, org_id, independence_key="k1")

    class _Provider(LLMProvider):
        name = "fake"
        model = "m"

        def evaluate_job(self, context: dict):
            return (
                AIEvalOut.model_validate(
                    {"summary": "", "scores": {"fit": 80}, "risk_level": "medium",
                     "confidence": "medium"}
                ),
                "job_evaluation_v1",
            )

        def extract_job(self, jd_text):
            raise NotImplementedError

        def summarize_reputation(self, context):
            raise NotImplementedError

    # 走完整评估：evidence 进入 context 并建立链接
    evaluate_job(db_session, db_session.get(__import__("app.models", fromlist=["Job"]).Job, job["id"]), _Provider())
    db_session.commit()
    assert db_session.query(EvaluationEvidence).count() == 1

    assert client.delete(f"/api/evidence/{ev['id']}").status_code == 204
    db_session.expire_all()
    assert db_session.query(EvaluationEvidence).count() == 0  # 无悬挂引用


def test_create_evidence_missing_job(client):
    assert client.post("/api/evidence/jobs/999", json={"claim": "x"}).status_code == 404


# ---------- 确定性风评统计 ----------

def test_aggregate_counts_and_eligibility(client, sample_job_with_evidence):
    """独立来源去重、正负分组、等级、时间跨度与 eligibility 规则。"""
    _, org_id = sample_job_with_evidence
    # 同一信息源的两条（同 key，一正一负 → 该源算 negative）
    _evidence(client, org_id, independence_key="src_a", stance="negative", published_at="2024-03-01")
    _evidence(client, org_id, independence_key="src_a", stance="positive", published_at="2024-06-01")
    # 独立第二源，B 级第一手
    _evidence(client, org_id, independence_key="src_b", evidence_level="B", stance="negative",
              published_at="2026-01-15")
    # 转载：跟随 src_b，不单独计数
    first = client.get(f"/api/evidence?organization_id={org_id}").json()
    src_b_id = next(e["id"] for e in first if e.get("independence_key") == "src_b")
    _evidence(client, org_id, repost_of_evidence_id=src_b_id, stance="negative")

    report = client.get(f"/api/organizations/{org_id}/reputation").json()
    topic = next(t for t in report["topics"] if t["topic"] == "startup_funding_fulfillment")
    # 独立源：src_a + src_b = 2（转载跟随 src_b）
    assert topic["independent_sources"] == 2
    # 组级 stance：src_a 组内一负即负（保守归类），src_b 负 → 2 个负源、0 个正源
    assert topic["positive_sources"] == 0
    assert topic["negative_sources"] == 2
    assert set(topic["evidence_levels"]) >= {"B", "C"}
    assert topic["eligible_for_scoring"] is True  # 2 独立 + 含 B
    assert topic["time_start"] == "2024-03-01"
    assert topic["time_end"] == "2026-01-15"


def test_single_source_topic_is_ineligible_clue_only(client, sample_job_with_evidence):
    """单条 C 级帖子是情报线索，不能自动变成定量风评分依据。"""
    _, org_id = sample_job_with_evidence
    _evidence(client, org_id, independence_key="lonely_src")

    report = client.get(f"/api/organizations/{org_id}/reputation").json()
    topic = next(t for t in report["topics"] if t["topic"] == "startup_funding_fulfillment")
    assert topic["independent_sources"] == 1
    assert topic["eligible_for_scoring"] is False
    assert "仅作情报参考" in topic["eligible_reason"]


def test_unknown_scope_downgraded_to_clue(client, sample_job_with_evidence):
    """Phase 6 核心策略：unknown scope 不能自动升级成全校通用证据。"""
    _, org_id = sample_job_with_evidence
    _evidence(client, org_id, claim="不知道是学院还是学校的说法",
              scope_level="unknown", independence_key="unknown_1")

    report = client.get(f"/api/organizations/{org_id}/reputation").json()
    # 不进主题计量
    assert all(t["independent_sources"] == 0 for t in report["topics"]) or report["topics"] == []
    # 作为情报线索明确列出
    assert any(c["evidence_id"] for c in report["clues"])
    assert any("仅作情报线索" in c["reason"] for c in report["clues"])
    # 整体可信度 low（没有 eligible 主题）
    assert report["overall_confidence"] == "low"


def test_department_filter(client, sample_job_with_evidence):
    _, org_id = sample_job_with_evidence
    _evidence(client, org_id, claim="化学学院证据", scope_level="department", scope_name="化学学院")
    _evidence(client, org_id, claim="医学院证据", scope_level="department", scope_name="医学院",
              independence_key="med_1")

    # 不限定院系：两条都计入
    report = client.get(f"/api/organizations/{org_id}/reputation").json()
    assert report["clues"] == []

    # 限定化学学院：医学院证据降为线索
    report = client.get(
        f"/api/organizations/{org_id}/reputation", params={"department": "化学学院"}
    ).json()
    assert any("医学院" in c["claim"] for c in report["clues"])


# ---------- AI 主题综合 ----------

class _ReputationProvider(LLMProvider):
    name = "fake_rep"
    model = "m"

    def __init__(self):
        self.context = None

    def summarize_reputation(self, context: dict):
        self.context = context
        return (
            ReputationSynthesisOut.model_validate(
                {
                    "topics": [
                        {"topic": "startup_funding_fulfillment",
                         "conclusion": "统计显示启动经费到账偏慢的反馈较多，建议核实到账条款。"}
                    ],
                    "overall_note": "样本有限",
                    "confidence": "medium",
                }
            ),
            "reputation_summary_v2",
        )

    def extract_job(self, jd_text):
        raise NotImplementedError

    def evaluate_job(self, context):
        raise NotImplementedError


def test_synthesize_merges_ai_conclusions_with_deterministic_counts(
    client, sample_job_with_evidence, monkeypatch
):
    """AI 只写结论；来源数/等级/eligibility 等数字仍来自确定性统计。"""
    from app.api.deps import get_ai_provider

    _, org_id = sample_job_with_evidence
    _evidence(client, org_id, independence_key="src_a")
    _evidence(client, org_id, independence_key="src_b", evidence_level="B")

    provider = _ReputationProvider()
    client.app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        resp = client.post(f"/api/organizations/{org_id}/reputation/synthesize")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["synthesized_by_ai"] is True
        assert data["prompt_version"] == "reputation_summary_v2"
        topic = next(t for t in data["topics"] if t["topic"] == "startup_funding_fulfillment")
        # 数字是确定性统计（2 独立源），不是 AI 编的
        assert topic["independent_sources"] == 2
        assert topic["ai_conclusion"].startswith("统计显示")
        # AI 看到了后端统计
        assert provider.context["statistics"][0]["independent_sources"] == 2
    finally:
        client.app.dependency_overrides.pop(get_ai_provider, None)


def test_synthesize_requires_ai(client, sample_job_with_evidence):
    _, org_id = sample_job_with_evidence
    resp = client.post(f"/api/organizations/{org_id}/reputation/synthesize")
    assert resp.status_code == 503


def test_deterministic_report_never_calls_ai(client, sample_job_with_evidence):
    """GET 报告是纯确定性统计，不需要 AI 配置。"""
    _, org_id = sample_job_with_evidence
    _evidence(client, org_id)
    resp = client.get(f"/api/organizations/{org_id}/reputation")
    assert resp.status_code == 200
    assert resp.json()["synthesized_by_ai"] is False


# ---------- Evaluation 集成：unknown 证据不支撑 reputation 定量分 ----------

def test_unknown_scope_evidence_does_not_support_reputation_score(
    client, sample_job_with_evidence, db_session
):
    """unknown scope 证据可被模型看到（作参考），但 finalize 强制 reputation=null。"""
    from app.ai.provider import LLMProvider
    from app.ai.schemas import JobEvaluationOut as AIEvalOut
    from app.services.evaluation import evaluate_job

    job, org_id = sample_job_with_evidence
    resp = client.post(
        f"/api/evidence/jobs/{job['id']}",
        json={"claim": "未知来源的风评说法", "category": "assessment_pressure",
              "evidence_level": "C", "stance": "negative", "scope_level": "unknown"},
    )
    assert resp.status_code == 201

    class _Provider(LLMProvider):
        name = "fake"
        model = "m"

        def evaluate_job(self, context: dict):
            # 模型无视 eligible 标志擅自给 reputation 分
            assert context["evidence"][0]["eligible_for_reputation_scoring"] is False
            return (
                AIEvalOut.model_validate(
                    {"summary": "", "scores": {"fit": 80, "reputation": 85},
                     "risk_level": "medium", "confidence": "medium"}
                ),
                "job_evaluation_v1",
            )

        def extract_job(self, jd_text):
            raise NotImplementedError

        def summarize_reputation(self, context):
            raise NotImplementedError

    evaluation = evaluate_job(
        db_session, db_session.get(__import__("app.models", fromlist=["Job"]).Job, job["id"]), _Provider()
    )
    db_session.commit()
    # unknown scope 证据不能支撑定量分
    assert evaluation.reputation_score is None


def test_eligible_scope_evidence_allows_reputation_score(
    client, sample_job_with_evidence, db_session
):
    """有 eligible（非 unknown）证据时，AI 的 reputation 分被接受。"""
    from app.ai.provider import LLMProvider
    from app.ai.schemas import JobEvaluationOut as AIEvalOut
    from app.services.evaluation import evaluate_job

    job, org_id = sample_job_with_evidence
    resp = client.post(
        f"/api/evidence/jobs/{job['id']}",
        json={"claim": "官方考核文件摘录", "category": "fact", "evidence_level": "A",
              "stance": "neutral", "scope_level": "job"},
    )
    assert resp.status_code == 201

    class _Provider(LLMProvider):
        name = "fake"
        model = "m"

        def evaluate_job(self, context: dict):
            assert context["evidence"][0]["eligible_for_reputation_scoring"] is True
            return (
                AIEvalOut.model_validate(
                    {"summary": "", "scores": {"fit": 80, "reputation": 70},
                     "risk_level": "low", "confidence": "high"}
                ),
                "job_evaluation_v1",
            )

        def extract_job(self, jd_text):
            raise NotImplementedError

        def summarize_reputation(self, context):
            raise NotImplementedError

    evaluation = evaluate_job(
        db_session, db_session.get(__import__("app.models", fromlist=["Job"]).Job, job["id"]), _Provider()
    )
    db_session.commit()
    assert evaluation.reputation_score == 70
