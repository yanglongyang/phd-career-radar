from tests.conftest import JOB_PAYLOAD


def test_academic_details_null_by_default(client, sample_job):
    resp = client.get(f"/api/jobs/{sample_job['id']}/academic-details")
    assert resp.status_code == 200
    assert resp.json() is None
    assert client.get(f"/api/jobs/{sample_job['id']}").json()["academic_details"] is None


def test_create_academic_details(client, sample_job):
    """正交四轴可同时表达：非事业编 + 预聘 + 固定期限合同 + 学校经费。"""
    resp = client.patch(
        f"/api/jobs/{sample_job['id']}/academic-details",
        json={
            "establishment_status": "non_established",
            "tenure_status": "tenure_track",
            "contract_type": "fixed_term",
            "funding_source": "university",
            "contract_years": 6,
            "is_up_or_out": True,
            "startup_funding": "50 万元",
            "startup_funding_terms": "分三年到账",
            "can_supervise_master": True,
            "can_supervise_phd": False,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["tenure_status"] == "tenure_track"
    assert data["contract_type"] == "fixed_term"  # 与 tenure_track 并存
    assert data["is_up_or_out"] is True
    assert data["can_supervise_phd"] is False

    detail = client.get(f"/api/jobs/{sample_job['id']}").json()
    assert detail["academic_details"]["funding_source"] == "university"


def test_partial_update_academic_details(client, sample_job):
    url = f"/api/jobs/{sample_job['id']}/academic-details"
    client.patch(url, json={"tenure_status": "tenure_track", "contract_years": 6})
    # 只改一个字段，其它保留
    resp = client.patch(url, json={"contract_years": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["contract_years"] == 3
    assert data["tenure_status"] == "tenure_track"
    # 显式传 null = 重置为未知
    resp = client.patch(url, json={"contract_years": None})
    assert resp.json()["contract_years"] is None


def test_axis_null_coerced_to_unknown(client, sample_job):
    """Phase 2.1.1 P0-1：四轴显式 null 归一化为 "unknown"，不写数据库 NULL。"""
    url = f"/api/jobs/{sample_job['id']}/academic-details"
    resp = client.patch(url, json={"tenure_status": "tenure_track"})
    assert resp.json()["tenure_status"] == "tenure_track"
    # 显式 null → unknown（不是 None）
    resp = client.patch(url, json={"tenure_status": None, "funding_source": None})
    data = resp.json()
    assert data["tenure_status"] == "unknown"
    assert data["funding_source"] == "unknown"
    # 未提供的轴保持不变
    assert data["establishment_status"] == "unknown"


def test_academic_details_invalid_value_rejected(client, sample_job):
    resp = client.patch(
        f"/api/jobs/{sample_job['id']}/academic-details",
        json={"establishment_status": "somehow"},
    )
    assert resp.status_code == 422


def test_delete_job_cascades_academic_details(client, sample_job, db_session):
    from app.models import AcademicJobDetails

    url = f"/api/jobs/{sample_job['id']}/academic-details"
    client.patch(url, json={"tenure_status": "tenure_track"})
    assert db_session.query(AcademicJobDetails).count() == 1

    assert client.delete(f"/api/jobs/{sample_job['id']}").status_code == 204
    assert db_session.query(AcademicJobDetails).count() == 0
    assert client.get(url).status_code == 404


def test_enterprise_job_has_no_academic_details(client):
    resp = client.post(
        "/api/jobs",
        json={
            "title": "计算化学研究员",
            "organization_name": "某药企",
            "job_category": "industry_rnd",
            "city": "上海",
            "description_raw": "负责药物分子设计。",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["academic_details"] is None
    assert client.get(f"/api/jobs/{resp.json()['id']}/academic-details").json() is None


def test_create_job_payload_unused_fields_ok(client):
    """JOB_PAYLOAD 含薪资标准化字段，创建应全部持久化。"""
    detail = client.get(f"/api/jobs/{client.post('/api/jobs', json=JOB_PAYLOAD).json()['id']}").json()
    assert detail["guaranteed_salary_min"] == 22
    assert detail["advertised_total_max"] is None
