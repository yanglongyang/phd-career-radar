import pytest

from app.ai.provider import AIError, LLMProvider
from app.ai.schemas import JobExtractionOut
from app.api.deps import get_ai_provider
from app.services.web import html_to_text

EXTRACTED = {
    "title": "预聘副教授（化学生物学）",
    "organization": "某某大学",
    "department": "化学学院",
    "job_category": "university_faculty",
    "province": "江苏",
    "city": "南京",
    "establishment_status": "non_established",
    "tenure_status": "tenure_track",
    "contract_type": "fixed_term",
    "funding_source": "university",
    "is_up_or_out": True,
    "contract_years": 6,
    "startup_funding": "50 万元",
    "salary_text": "年薪 30-45 万",
    "salary_currency": "CNY",
    "salary_period": "year",
    "unknowns": ["首聘周期", "国自然是否为硬性要求", "启动经费到账方式"],
}

LONG_TEXT = (
    "某某大学化学学院面向海内外公开招聘预聘副教授。"
    "申请人应具有有机化学或化学生物学博士学位，研究方向为荧光探针。"
    "学校提供启动经费 50 万元，年薪 30-45 万，聘期六年，中期考核以正式文件为准。"
)


class FakeProvider(LLMProvider):
    name = "fake"
    model = "fake-model"

    def __init__(self, fail=False):
        self.calls: list[str] = []
        self.fail = fail

    def extract_job(self, jd_text: str):
        self.calls.append(jd_text)
        if self.fail:
            raise AIError("模拟 AI 调用失败")
        return JobExtractionOut.model_validate(EXTRACTED), "job_extraction_v1"

    def evaluate_job(self, context: dict):
        raise NotImplementedError("Phase 4")

    def summarize_reputation(self, evidence: list[dict]):
        raise NotImplementedError("Phase 6")


@pytest.fixture()
def fake_provider(client):
    provider = FakeProvider()
    client.app.dependency_overrides[get_ai_provider] = lambda: provider
    yield provider
    client.app.dependency_overrides.pop(get_ai_provider, None)


def test_extract_requires_ai_config(client):
    """AI 未配置 → 503 明确提示，不伪造结果。"""
    resp = client.post("/api/jobs/extract-preview", json={"text": LONG_TEXT})
    assert resp.status_code == 503
    assert "AI 未配置" in resp.text


def test_extract_needs_text_or_url(client):
    resp = client.post("/api/jobs/extract-preview", json={})
    assert resp.status_code == 422


def test_extract_text_too_short(client, fake_provider):
    resp = client.post("/api/jobs/extract-preview", json={"text": "招聘"})
    assert resp.status_code == 422
    assert "过短" in resp.text


def test_extract_preview_from_text(client, fake_provider):
    resp = client.post("/api/jobs/extract-preview", json={"text": LONG_TEXT})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source_text"] == LONG_TEXT
    assert data["extraction"]["title"] == "预聘副教授（化学生物学）"
    # 正交四轴可以同时表达
    assert data["extraction"]["tenure_status"] == "tenure_track"
    assert data["extraction"]["contract_type"] == "fixed_term"
    assert data["extraction"]["establishment_status"] == "non_established"
    assert data["extraction"]["is_up_or_out"] is True
    # 审计信息与信息缺口随预览返回，供用户确认
    assert data["prompt_version"] == "job_extraction_v1"
    assert data["provider"] == "fake"
    assert data["model"] == "fake-model"
    assert "国自然是否为硬性要求" in data["extraction"]["unknowns"]
    # AI 实际收到的就是用户提交的正文
    assert fake_provider.calls == [LONG_TEXT]


def test_extract_url_fetch_failure(client, fake_provider, monkeypatch):
    """URL 抓取失败 → 422 + 提示粘贴正文，不编写反爬对抗。"""
    from app.services.web import PageFetchError

    monkeypatch.setattr(
        "app.api.routes.jobs.fetch_url_text",
        lambda url: (_ for _ in ()).throw(PageFetchError("网页访问失败，请直接粘贴公告全文")),
    )
    resp = client.post("/api/jobs/extract-preview", json={"url": "https://example.edu.cn/hr/1"})
    assert resp.status_code == 422
    assert "粘贴" in resp.text


def test_extract_url_success(client, fake_provider, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.jobs.fetch_url_text", lambda url: f"{LONG_TEXT}（来自 {url}）"
    )
    resp = client.post("/api/jobs/extract-preview", json={"url": "https://example.edu.cn/hr/1"})
    assert resp.status_code == 200
    assert fake_provider.calls[0].endswith("（来自 https://example.edu.cn/hr/1）")


def test_extract_ai_error_returns_502(client, fake_provider):
    fake_provider.fail = True
    resp = client.post("/api/jobs/extract-preview", json={"text": LONG_TEXT})
    assert resp.status_code == 502
    assert "AI 解析失败" in resp.text


def test_create_with_nested_academic_details(client):
    """Phase 3：解析确认后岗位 + 高校字段一次原子入库。"""
    payload = {
        "title": "预聘副教授（化学生物学）",
        "organization_name": "某某大学",
        "department": "化学学院",
        "job_category": "university_faculty",
        "province": "江苏",
        "city": "南京",
        "salary_text": "年薪 30-45 万",
        "description_raw": LONG_TEXT,
        "academic_details": {
            "establishment_status": "non_established",
            "tenure_status": "tenure_track",
            "contract_type": "fixed_term",
            "funding_source": "university",
            "is_up_or_out": True,
            "contract_years": 6,
            "startup_funding": "50 万元",
        },
    }
    resp = client.post("/api/jobs", json=payload)
    assert resp.status_code == 201, resp.text
    detail = resp.json()
    academic = detail["academic_details"]
    assert academic is not None
    assert academic["tenure_status"] == "tenure_track"
    assert academic["contract_type"] == "fixed_term"
    assert academic["is_up_or_out"] is True
    # 未提供的轴保持数据库默认 unknown
    assert academic["establishment_status"] == "non_established"
    resp = client.get(f"/api/jobs/{detail['id']}/academic-details")
    assert resp.json()["funding_source"] == "university"


def test_create_nested_details_unknown_on_conflict_fields(client):
    """嵌套 academic_details 显式 null 轴同样归一为 unknown。"""
    resp = client.post(
        "/api/jobs",
        json={
            "title": "研究员",
            "organization_name": "某院",
            "academic_details": {"establishment_status": None},
        },
    )
    assert resp.status_code == 201
    assert resp.json()["academic_details"]["establishment_status"] == "unknown"


def test_html_to_text_extracts_readability():
    html = """
    <html><head><style>body{color:red}</style></head>
    <body>
      <script>var tracking = 1;</script>
      <!-- 注释 -->
      <div><p>某某大学化学学院公开招聘。</p><p>提供启动经费 50 万元。</p></div>
    </body></html>
    """
    text = html_to_text(html)
    assert "某某大学化学学院公开招聘。" in text
    assert "启动经费" in text
    assert "tracking" not in text
    assert "color" not in text
