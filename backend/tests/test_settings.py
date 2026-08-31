"""Phase 7：Settings API（读写 config/*.yaml）与批量重评测试。"""


from app.core.config import CONFIG_DIR


def test_get_settings_returns_current_config(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "scoring.yaml" in data
    assert data["scoring.yaml"]["scoring"]["fit"] == 20


def test_update_scoring_validates_total_100(client):
    resp = client.put(
        "/api/settings",
        json={"scoring_yaml": {"scoring": {"fit": 20, "region": 10}}},
    )
    assert resp.status_code == 422
    assert "100" in resp.text


def test_update_settings_roundtrip(client, monkeypatch):
    """写回 config 后 GET 读到新值；完成后恢复原配置。"""
    original = (CONFIG_DIR / "regions.yaml").read_text(encoding="utf-8")
    try:
        resp = client.put(
            "/api/settings",
            json={"regions_yaml": {"preferred": ["南京"], "acceptable": ["杭州"],
                                   "neutral": [], "avoid": []}},
        )
        assert resp.status_code == 200
        assert "regions.yaml" in resp.json()["written"]

        data = client.get("/api/settings").json()
        assert data["regions.yaml"]["preferred"] == ["南京"]
        # 地区引擎立即生效
        assert client.get("/api/health").status_code == 200
    finally:
        (CONFIG_DIR / "regions.yaml").write_text(original, encoding="utf-8")


def test_update_settings_unknown_file_rejected(client):
    resp = client.put("/api/settings", json={"other.yaml": {}})
    assert resp.status_code == 422
    assert "Extra inputs are not permitted" in resp.text  # extra=forbid 显式失败


def test_update_settings_bad_hard_filters(client):
    resp = client.put(
        "/api/settings",
        json={"profile_yaml": {"hard_filters": {"minimum_salary": "abc"}}},
    )
    assert resp.status_code == 422


def test_re_evaluate_all_requires_ai(client, sample_job):
    resp = client.post("/api/jobs/re-evaluate-all")
    assert resp.status_code == 503


def test_re_evaluate_all_runs_all_jobs(client, sample_job, monkeypatch):
    """批量重评：全部岗位逐个评估并汇总；单点失败不中断。"""
    from app.ai.provider import AIError, LLMProvider
    from app.ai.schemas import JobEvaluationOut as AIEvalOut
    from app.api.deps import get_ai_provider

    second = client.post(
        "/api/jobs",
        json={"title": "第二个岗位", "organization_name": "批量测试大学",
              "description_raw": "批量重评测试岗位二。"},
    ).json()

    class _BatchProvider(LLMProvider):
        name = "fake_batch"
        model = "m"

        def __init__(self):
            self.calls = 0

        def evaluate_job(self, context: dict):
            self.calls += 1
            if self.calls == 1:
                raise AIError("第一个岗位模拟失败")
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

    provider = _BatchProvider()
    client.app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        resp = client.post("/api/jobs/re-evaluate-all")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 2
        assert len(data["failed"]) == 1
        assert data["failed"][0]["job_id"] == sample_job["id"]
        assert data["succeeded"] == [second["id"]]
    finally:
        client.app.dependency_overrides.pop(get_ai_provider, None)
