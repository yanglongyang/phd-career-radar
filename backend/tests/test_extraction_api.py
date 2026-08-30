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
    "country": "中国",
    "province": "江苏",
    "city": "南京",
    "employment_type": "全职",
    "posted_at": "2026-08-20",
    "deadline": "2026-10-31",
    "degree_requirement": "博士",
    "experience_requirement": None,
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


def test_extract_needs_exactly_one_of_text_or_url(client, fake_provider):
    """Phase 3.1：text/url 必须二选一 —— 都不传或同时传都是 422，不静默挑一个。"""
    resp = client.post("/api/jobs/extract-preview", json={})
    assert resp.status_code == 422
    resp = client.post(
        "/api/jobs/extract-preview", json={"text": LONG_TEXT, "url": "https://example.com/a"}
    )
    assert resp.status_code == 422
    assert "只能提供一个" in resp.text


def test_extract_text_too_short(client, fake_provider):
    resp = client.post("/api/jobs/extract-preview", json={"text": "招聘"})
    assert resp.status_code == 422
    assert "过短" in resp.text


def test_extract_text_too_long_rejected(client):
    """Phase 3.1：正文超过上限 → 422 明确报错（内存与 token 成本保护）。"""
    from app.schemas.extraction import MAX_TEXT_CHARS

    resp = client.post("/api/jobs/extract-preview", json={"text": "字" * (MAX_TEXT_CHARS + 1)})
    assert resp.status_code == 422


def test_extract_preview_from_text(client, fake_provider):
    resp = client.post("/api/jobs/extract-preview", json={"text": LONG_TEXT})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source_type"] == "text"
    assert data["source_url"] is None  # 文本来源没有 URL，避免保存时串单
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
    data = resp.json()
    assert data["source_type"] == "url"
    assert data["source_url"] == "https://example.edu.cn/hr/1"  # provenance 随预览返回
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


def test_ssrf_guard_rejects_non_public_hosts():
    """Phase 3.1：URL 抓取只允许公网可路由 IP，内网/回环一律拒绝。"""
    from app.services.web import PageFetchError, assert_public_host, fetch_url_text

    for host in ("127.0.0.1", "192.168.1.1", "10.0.0.5", "172.16.0.9", "169.254.1.1", "0.0.0.0"):
        with pytest.raises(PageFetchError, match="非公网"):
            assert_public_host(host)
    for url in ("http://127.0.0.1:8000/x", "http://localhost/a", "http://192.168.1.1/x"):
        with pytest.raises(PageFetchError):
            fetch_url_text(url)
    # 公网 IP 通过校验
    assert_public_host("8.8.8.8")


def test_import_audit_persisted(client, fake_provider, db_session):
    """Phase 3.1：AI 导入审计随保存持久化（provider/prompt/原始输出/确认 payload/正文哈希）。"""
    from app.core.hash import sha256_text
    from app.models import JobImportRecord

    resp = client.post("/api/jobs/extract-preview", json={"text": LONG_TEXT})
    preview = resp.json()
    payload = {
        "title": preview["extraction"]["title"],
        "organization_name": preview["extraction"]["organization"],
        "description_raw": preview["source_text"],
        "academic_details": {
            "tenure_status": preview["extraction"]["tenure_status"],
            "contract_years": preview["extraction"]["contract_years"],
        },
        "import_audit": {
            "ingestion_method": "text",
            "source_url": preview["source_url"],
            "provider": preview["provider"],
            "model": preview["model"],
            "prompt_version": preview["prompt_version"],
            "extraction_json": preview["extraction"],
        },
    }
    created = client.post("/api/jobs", json=payload)
    assert created.status_code == 201, created.text

    row = db_session.query(JobImportRecord).filter_by(job_id=created.json()["id"]).one()
    assert row.ingestion_method == "text"
    assert row.provider == "fake"
    assert row.model == "fake-model"
    assert row.prompt_version == "job_extraction_v1"
    assert row.extraction_json["title"] == "预聘副教授（化学生物学）"
    assert row.confirmed_payload_json["title"] == "预聘副教授（化学生物学）"
    assert "import_audit" not in row.confirmed_payload_json
    assert row.source_text_hash == sha256_text(LONG_TEXT)


def test_full_sample_end_to_end_field_mapping(client, db_session):
    """审查要求的核心测试：AI 返回完整样例 → 按前端同一映射构造 payload → 不修改 →
    保存 → 逐字段核对数据库。任何"解析出来但保存丢失"的字段都会在这里失败。"""
    payload = {
        "title": EXTRACTED["title"],
        "organization_name": EXTRACTED["organization"],
        "department": EXTRACTED["department"],
        "job_category": EXTRACTED["job_category"],
        "country": EXTRACTED["country"],
        "province": EXTRACTED["province"],
        "city": EXTRACTED["city"],
        "employment_type": EXTRACTED["employment_type"],
        "posted_at": EXTRACTED["posted_at"],
        "deadline": EXTRACTED["deadline"],
        "degree_requirement": EXTRACTED["degree_requirement"],
        "experience_requirement": None,  # AI 输出 null → 保存 null（未知）
        "salary_text": EXTRACTED["salary_text"],
        "salary_currency": EXTRACTED["salary_currency"],
        "salary_period": EXTRACTED["salary_period"],
        "description_raw": LONG_TEXT,
        "academic_details": {
            "establishment_status": EXTRACTED["establishment_status"],
            "tenure_status": EXTRACTED["tenure_status"],
            "contract_type": EXTRACTED["contract_type"],
            "funding_source": EXTRACTED["funding_source"],
            "is_up_or_out": EXTRACTED["is_up_or_out"],
            "contract_years": EXTRACTED["contract_years"],  # number 直传
            "startup_funding": EXTRACTED["startup_funding"],
            "master_quota": "2",  # 文本字段即使是纯数字也保持字符串
        },
        "import_audit": {
            "ingestion_method": "text",
            "provider": "fake",
            "prompt_version": "job_extraction_v1",
            "extraction_json": EXTRACTED,
        },
    }
    created = client.post("/api/jobs", json=payload)
    assert created.status_code == 201, created.text
    detail = client.get(f"/api/jobs/{created.json()['id']}").json()

    # 基本字段：此前会丢失的六个字段逐一核对
    assert detail["country"] == "中国"
    assert detail["posted_at"] == "2026-08-20"
    assert detail["deadline"] == "2026-10-31"
    assert detail["employment_type"] == "全职"
    assert detail["degree_requirement"] == "博士"
    assert detail["experience_requirement"] is None
    assert detail["salary_currency"] == "CNY"
    # 高校字段：contract_years 不再被类型转换吞掉
    academic = detail["academic_details"]
    assert academic["contract_years"] == 6
    assert academic["tenure_status"] == "tenure_track"
    assert academic["is_up_or_out"] is True
    assert academic["master_quota"] == "2"  # 字符串字段不被转成数字


def test_extraction_prompt_matches_schema():
    """Phase 3.1：Extraction Prompt 必须覆盖 Schema 的每个字段（一致性检查）。"""
    from app.ai.prompts import get_prompt
    from app.ai.schemas import JobExtractionOut

    _, text = get_prompt("job_extraction")
    missing = [name for name in JobExtractionOut.model_fields if name not in text]
    assert missing == [], f"Prompt 缺少字段说明: {missing}"
    assert "position_nature" not in text  # legacy 字段不得回流
    assert "annual_salary" not in text  # 孤立字段不得回流
