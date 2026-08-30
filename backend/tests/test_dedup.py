from tests.conftest import JOB_PAYLOAD


def test_create_and_duplicate_conflict(client, sample_job):
    # 同样的岗位再次提交 → 409 + 指出重复对象
    resp = client.post("/api/jobs", json=JOB_PAYLOAD)
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["duplicate_of"]["id"] == sample_job["id"]

    # 用户确认后允许强制创建
    resp2 = client.post("/api/jobs", json={**JOB_PAYLOAD, "allow_duplicate": True})
    assert resp2.status_code == 201
    assert resp2.json()["id"] != sample_job["id"]


def test_duplicate_by_description_similarity(client, sample_job):
    # 标题略不同但同单位、公告文本高度相似 → 仍识别为重复
    payload = {
        **JOB_PAYLOAD,
        "title": "青年研究员（化学生物学方向）",
        "description_raw": "招聘具有有机化学、荧光探针研究背景的青年人才，提供启动经费 50 万元。",
    }
    resp = client.post("/api/jobs", json=payload)
    assert resp.status_code == 409


def test_different_job_not_flagged(client, sample_job):
    payload = {
        **JOB_PAYLOAD,
        "title": "计算数学博士后",
        "job_category": "postdoc",
        "city": "上海",
        "description_raw": "诚聘计算数学方向博士后，从事数值模拟与偏微分方程研究。",
    }
    resp = client.post("/api/jobs", json=payload)
    assert resp.status_code == 201
