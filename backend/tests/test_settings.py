"""Phase 7 / 7.1：Settings API（读写 config/*.yaml）与批量重评测试。

Settings 写盘测试一律使用 monkeypatch CONFIG_DIR 指向 tmp_path，
**不修改真实仓库 config/ 目录**（Phase 7.1：pytest 不得污染 Git working tree）。
"""

import pytest
import yaml

from app.core import config as config_module
from app.services import settings as settings_service

INITIAL_FILES = {
    "scoring.yaml": {
        "scoring": {
            "fit": 20, "career_stability": 15, "research_resources": 15,
            "region": 15, "compensation": 10, "reputation": 10,
            "workload": 5, "long_term": 10,
        },
        "region_tier_scores": {"preferred": 90, "acceptable": 70,
                               "neutral": 50, "avoid": 20},
    },
    "regions.yaml": {"preferred": [], "acceptable": [], "neutral": [], "avoid": []},
    "profile.yaml": {"hard_filters": {}},
}


@pytest.fixture()
def config_dir(monkeypatch, tmp_path):
    """配置目录指向 tmp_path（config.py 与 settings.py 双 patch），
    前后清理 lru_cache —— 测试不触碰真实仓库 config/。"""
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings_service, "CONFIG_DIR", tmp_path)
    for name, data in INITIAL_FILES.items():
        (tmp_path / name).write_text(
            yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
        )
    config_module.load_yaml_config.cache_clear()
    yield tmp_path
    config_module.load_yaml_config.cache_clear()


def test_get_settings_returns_current_config(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "scoring.yaml" in data
    assert data["scoring.yaml"]["scoring"]["fit"] == 20


def test_update_scoring_missing_dimension_rejected(client):
    resp = client.put(
        "/api/settings",
        json={"scoring_yaml": {"scoring": {"fit": 20, "region": 10}}},
    )
    assert resp.status_code == 422
    assert "8 维必须齐全" in resp.text


def test_update_scoring_negative_or_non_numeric_rejected(client):
    resp = client.put(
        "/api/settings",
        json={"scoring_yaml": {"scoring": {
            "fit": 20, "career_stability": 15, "research_resources": 15,
            "region": 15, "compensation": 10, "reputation": 10,
            "workload": -5, "long_term": 10,
        }}},
    )
    assert resp.status_code == 422
    assert "不能为负" in resp.text

    resp = client.put(
        "/api/settings",
        json={"scoring_yaml": {"scoring": {
            "fit": 20, "career_stability": 15, "research_resources": 15,
            "region": 15, "compensation": 10, "reputation": 10,
            "workload": "高", "long_term": 10,
        }}},
    )
    assert resp.status_code == 422


def test_update_settings_roundtrip_with_cache_invalidation(client, config_dir):
    """P0-1：写入后配置缓存立即失效 —— 先预热旧 cache，PUT 新 regions 后
    地区引擎必须立即读到新值（不再返回旧缓存）。"""

    # 预热 cache：先读一次旧配置
    from app.services.regions import get_region_tier

    assert get_region_tier("江苏", "南京") == "unrated"

    resp = client.put(
        "/api/settings",
        json={"regions_yaml": {"preferred": ["南京"], "acceptable": ["杭州"],
                               "neutral": [], "avoid": []}},
    )
    assert resp.status_code == 200

    # 地区引擎立即生效（cache_clear 后重新加载）
    assert get_region_tier("江苏", "南京") == "preferred"
    from app.services.regions import get_region_score

    assert get_region_score("江苏", "南京") == 90.0
    # GET /settings 也读到新值
    assert client.get("/api/settings").json()["regions.yaml"]["preferred"] == ["南京"]


def test_update_settings_hard_filters_boolean_strict(client, config_dir):
    """字符串 "false" 不得通过 —— 三个排除开关必须真正的 boolean。"""
    resp = client.put(
        "/api/settings",
        json={"profile_yaml": {"hard_filters": {
            "unacceptable_regions": [],
            "minimum_salary": None,
            "reject_pi_funded": False,
            "reject_postdoc": "false",  # 字符串真值陷阱
            "reject_high_risk_tenure_track": False,
        }}},
    )
    assert resp.status_code == 422
    assert "reject_postdoc" in resp.text

    resp = client.put(
        "/api/settings",
        json={"profile_yaml": {"hard_filters": {"unacceptable_regions": "南京"}}},
    )
    assert resp.status_code == 422
    assert "列表" in resp.text


def test_update_settings_unknown_file_rejected(client):
    resp = client.put("/api/settings", json={"other.yaml": {}})
    assert resp.status_code == 422
    assert "Extra inputs are not permitted" in resp.text  # extra=forbid 显式失败


def test_update_settings_creates_no_bak_in_repo(client, config_dir):
    """设置写盘发生在 tmp_path，不产生真实仓库 .bak。"""
    client.put(
        "/api/settings",
        json={"regions_yaml": {"preferred": ["南京"], "acceptable": [],
                               "neutral": [], "avoid": []}},
    )
    assert (config_dir / "regions.yaml.bak").exists()
    # 真实仓库 config/ 目录（CONFIG_DIR 已被 patch，用 PROJECT_ROOT 定位）
    repo_config = config_module.PROJECT_ROOT / "config"

    assert not (repo_config / "regions.yaml.bak").exists()


def test_re_evaluate_all_requires_ai(client, sample_job):
    resp = client.post("/api/jobs/re-evaluate-all")
    assert resp.status_code == 503


def test_re_evaluate_all_independent_transactions(
    client, sample_job, monkeypatch, db_session
):
    """P0-2：success → fail → success 时，第 1、3 个岗位的 Evaluation
    必须真实落库（每岗位独立事务提交，不被后续 rollback 撤销）。"""
    from app.ai.provider import AIError, LLMProvider
    from app.ai.schemas import JobEvaluationOut as AIEvalOut
    from app.api.deps import get_ai_provider
    from app.models import JobEvaluation

    job2 = client.post(
        "/api/jobs",
        json={"title": "岗位二", "organization_name": "事务测试大学",
              "description_raw": "批量重评事务测试岗位二。"},
    ).json()
    job3 = client.post(
        "/api/jobs",
        json={"title": "岗位三", "organization_name": "事务测试大学",
              "description_raw": "批量重评事务测试岗位三。"},
    ).json()

    class _Provider(LLMProvider):
        name = "fake_txn"
        model = "m"

        def __init__(self):
            self.calls = 0

        def evaluate_job(self, context: dict):
            self.calls += 1
            if self.calls == 2:
                raise AIError("第二个岗位模拟失败")
            return (
                AIEvalOut.model_validate(
                    {"summary": "", "scores": {"fit": 80},
                     "risk_level": "low", "confidence": "high"}
                ),
                "job_evaluation_v2",
            )

        def extract_job(self, jd_text):
            raise NotImplementedError

        def summarize_reputation(self, context):
            raise NotImplementedError

    provider = _Provider()
    client.app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        resp = client.post("/api/jobs/re-evaluate-all")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 3
        assert data["succeeded"] == [sample_job["id"], job3["id"]]
        assert data["failed"][0]["job_id"] == job2["id"]

        # 关键断言：查数据库确认第 1、3 个真实落库（不被 rollback 撤销）
        db_session.expire_all()
        for job_id in (sample_job["id"], job3["id"]):
            assert (
                db_session.query(JobEvaluation).filter_by(job_id=job_id).count() == 1
            ), f"job {job_id} 的 Evaluation 应已落库"
        assert (
            db_session.query(JobEvaluation).filter_by(job_id=job2["id"]).count() == 0
        )
    finally:
        client.app.dependency_overrides.pop(get_ai_provider, None)
