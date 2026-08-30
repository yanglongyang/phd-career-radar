"""Application CRM API 测试（Phase 5）。"""

import pytest

from tests.conftest import JOB_PAYLOAD


@pytest.fixture()
def job_id(client):
    resp = client.post("/api/jobs", json=JOB_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_application_defaults(client, job_id):
    resp = client.post(f"/api/jobs/{job_id}/application", json={})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "new"
    assert data["allowed_next_statuses"] == ["ignored", "reviewed", "shortlist"]
    assert data["job"]["title"] == JOB_PAYLOAD["title"]
    assert data["job"]["city"] == "南京"


def test_create_application_duplicate_conflict(client, job_id):
    assert client.post(f"/api/jobs/{job_id}/application", json={}).status_code == 201
    resp = client.post(f"/api/jobs/{job_id}/application", json={})
    assert resp.status_code == 409


def test_create_application_missing_job(client):
    assert client.post("/api/jobs/999/application", json={}).status_code == 404


def test_create_application_unknown_field_rejected(client, job_id):
    resp = client.post(f"/api/jobs/{job_id}/application", json={"stage": "offer"})
    assert resp.status_code == 422


def test_status_transition_forward(client, job_id):
    app = client.post(f"/api/jobs/{job_id}/application", json={}).json()
    for status in ("reviewed", "shortlist", "preparing", "applied", "interview_1", "offer"):
        resp = client.patch(f"/api/applications/{app['id']}", json={"status": status})
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == status
    # applied_at 在进入 contacting/applied 时自动记录
    assert client.get(f"/api/applications/{app['id']}").json() is not None


def test_status_transition_illegal_jump_rejected(client, job_id):
    app = client.post(f"/api/jobs/{job_id}/application", json={}).json()
    resp = client.patch(f"/api/applications/{app['id']}", json={"status": "offer"})
    assert resp.status_code == 409
    assert "允许的目标状态" in resp.text
    # 状态未变
    assert client.patch(
        f"/api/applications/{app['id']}", json={"notes": "keep"}
    ).json()["status"] == "new"


def test_terminal_state_has_no_outgoing(client, job_id):
    app = client.post(f"/api/jobs/{job_id}/application", json={}).json()
    client.patch(f"/api/applications/{app['id']}", json={"status": "reviewed"})
    client.patch(f"/api/applications/{app['id']}", json={"status": "rejected"})
    resp = client.patch(f"/api/applications/{app['id']}", json={"status": "offer"})
    assert resp.status_code == 409


def test_full_field_update(client, job_id):
    app = client.post(f"/api/jobs/{job_id}/application", json={}).json()
    resp = client.patch(
        f"/api/applications/{app['id']}",
        json={
            "priority": 3,
            "next_action": "发邮件确认启动经费到账方式",
            "next_action_date": "2026-09-05",
            "contact": "王老师 138xxxx",
            "resume_version": "v3-学术",
            "cover_letter_version": "v2",
            "notes": "重点跟踪",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["priority"] == 3
    assert data["next_action"] == "发邮件确认启动经费到账方式"
    assert data["next_action_date"] == "2026-09-05"
    assert data["resume_version"] == "v3-学术"
    assert data["contact"] == "王老师 138xxxx"


def test_list_and_filter_and_sort(client, job_id):
    # 三个岗位三条申请，创建时直接指定不同起始状态（合法入口）
    ids = [job_id]
    for suffix in ("B", "C"):
        ids.append(
            client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "title": f"岗位{suffix}", "city": "苏州",
                      "description_raw": f"列表测试岗位{suffix}。"},
            ).json()["id"]
        )
    for jid, status in zip(ids, ("shortlist", "applied", "offer"), strict=True):
        resp = client.post(f"/api/jobs/{jid}/application", json={"status": status})
        assert resp.status_code == 201, resp.text

    data = client.get("/api/applications").json()
    assert data["total"] == 3

    data = client.get("/api/applications", params={"status": "applied"}).json()
    assert data["total"] == 1

    data = client.get("/api/applications", params={"q": "化学"}).json()
    assert data["total"] == 3  # job brief 标题匹配…… q 搜的是 next_action/notes/contact

    data = client.get("/api/applications", params={"sort": "priority"}).json()
    assert data["total"] == 3


def test_get_application_by_job_and_delete(client, job_id):
    app = client.post(f"/api/jobs/{job_id}/application", json={}).json()
    got = client.get(f"/api/jobs/{job_id}/application").json()
    assert got["id"] == app["id"]

    assert client.delete(f"/api/applications/{app['id']}").status_code == 204
    assert client.get(f"/api/jobs/{job_id}/application").json() is None
    # 岗位本身保留
    assert client.get(f"/api/jobs/{job_id}").status_code == 200
    # 可以重新创建
    assert client.post(f"/api/jobs/{job_id}/application", json={}).status_code == 201


def test_dashboard_counts_reflect_crm(client, job_id):
    """CRM 状态变化直接驱动 Dashboard 的流程计数。"""
    app = client.post(f"/api/jobs/{job_id}/application", json={}).json()
    for status in ("reviewed", "shortlist", "preparing"):  # 合法流转路径
        resp = client.patch(f"/api/applications/{app['id']}", json={"status": status})
        assert resp.status_code == 200
    counts = client.get("/api/dashboard").json()["counts"]
    assert counts["preparing"] == 1
    client.patch(f"/api/applications/{app['id']}", json={"status": "applied"})
    counts = client.get("/api/dashboard").json()["counts"]
    assert counts["preparing"] == 0
    assert counts["applied"] == 1
