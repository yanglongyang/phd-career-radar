from tests.conftest import JOB_PAYLOAD


def test_create_job_with_organization_autocreate(client, sample_job):
    assert sample_job["title"] == JOB_PAYLOAD["title"]
    assert sample_job["organization"]["name"] == "示例大学"
    assert sample_job["position_nature"] == "tenure_track"
    assert sample_job["status"] == "new"


def test_get_job_detail(client, sample_job):
    resp = client.get(f"/api/jobs/{sample_job['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["description_raw"].startswith("招聘具有")
    assert data["salary_max"] == 40
    assert data["guaranteed_salary_max"] == 26
    assert data["salary_currency"] == "CNY"
    assert data["versions"] == []
    assert data["academic_details"] is None  # 尚未填写高校详情


def test_list_filters_and_sort(client, sample_job):
    # 再建一个 shortlisted 状态的岗位（公告文本不同，避免触发同单位相似去重）
    resp = client.post(
        "/api/jobs",
        json={
            **JOB_PAYLOAD,
            "title": "博士后（计算化学）",
            "job_category": "postdoc",
            "city": "上海",
            "status": "shortlisted",
            "description_raw": "诚聘计算化学方向博士后，从事分子模拟与机器学习势函数研究。",
        },
    )
    assert resp.status_code == 201

    # 类别过滤
    data = client.get("/api/jobs", params={"job_category": "postdoc"}).json()
    assert data["total"] == 1 and data["items"][0]["job_category"] == "postdoc"

    # 状态过滤
    data = client.get("/api/jobs", params={"status": "shortlisted"}).json()
    assert data["total"] == 1 and data["items"][0]["title"].startswith("博士后")

    # 城市过滤
    data = client.get("/api/jobs", params={"city": "南京"}).json()
    assert data["total"] == 1

    # 关键词搜索
    data = client.get("/api/jobs", params={"q": "化学"}).json()
    assert data["total"] == 2

    # 排序：默认 first_seen_at desc（后建的在前）
    data = client.get("/api/jobs").json()
    assert data["items"][0]["title"].startswith("博士后")


def test_update_job_fields_and_user_decision_fields(client, sample_job):
    job_id = sample_job["id"]
    resp = client.patch(
        f"/api/jobs/{job_id}",
        json={"status": "reviewing", "user_rating": 4, "user_priority": 8, "user_notes": "重点跟踪启动经费到账方式"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "reviewing"
    assert data["user_rating"] == 4
    assert data["user_priority"] == 8
    assert data["user_notes"].startswith("重点")


def test_patch_invalid_status_rejected(client, sample_job):
    resp = client.patch(f"/api/jobs/{sample_job['id']}", json={"status": "hired_yesterday"})
    assert resp.status_code == 422


def test_job_rejects_workflow_statuses(client, sample_job):
    """Phase 2.1：Job 不再接受求职流程状态（applied/interviewing/offer/preparing）。"""
    for workflow_status in ("applied", "interviewing", "offer", "preparing"):
        resp = client.patch(f"/api/jobs/{sample_job['id']}", json={"status": workflow_status})
        assert resp.status_code == 422, workflow_status


def test_delete_job(client, sample_job):
    job_id = sample_job["id"]
    assert client.delete(f"/api/jobs/{job_id}").status_code == 204
    assert client.get(f"/api/jobs/{job_id}").status_code == 404


def test_dashboard_counts_split_job_and_application(client, sample_job, db_session):
    """Phase 2.1：to_review/focus 来自 Job；applied/interviewing/offer 来自 Application。"""
    from app.models import Application

    client.patch(f"/api/jobs/{sample_job['id']}", json={"status": "shortlisted"})

    # 每个岗位一条申请记录（Application.job_id 唯一；Application API 属于 Phase 5）
    for suffix, status in (("A", "applied"), ("B", "interview_1"), ("C", "offer")):
        resp = client.post(
            "/api/jobs",
            json={**JOB_PAYLOAD, "title": f"岗位{suffix}", "city": "苏州",
                  "description_raw": f"申请流程测试岗位{suffix}。"},
        )
        assert resp.status_code == 201, resp.text
        db_session.add(Application(job_id=resp.json()["id"], status=status))
    db_session.commit()

    data = client.get("/api/dashboard").json()
    assert data["counts"]["new_today"] == 4  # 今日新增与状态无关（1 + 新建 3 个）
    assert data["counts"]["focus"] == 1      # shortlisted 来自 Job
    assert data["counts"]["to_review"] == 3  # 新建的 3 个岗位仍是 new
    assert data["counts"]["applied"] == 1        # 来自 Application
    assert data["counts"]["interviewing"] == 1   # interview_1 计入面试中
    assert data["counts"]["offer"] == 1          # 来自 Application
    assert data["counts"]["preparing"] == 0
