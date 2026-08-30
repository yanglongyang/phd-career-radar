

def test_version_saved_on_salary_and_deadline_change(client, sample_job):
    job_id = sample_job["id"]
    resp = client.patch(
        f"/api/jobs/{job_id}",
        json={"salary_text": "年薪 35-45 万", "salary_max": 45, "deadline": "2026-10-15"},
    )
    assert resp.status_code == 200
    versions = resp.json()["versions"]
    assert len(versions) == 1
    changed_fields = {c["field"] for c in versions[0]["changes"]}
    assert changed_fields == {"salary_text", "salary_max", "deadline"}
    # 快照保存的是旧值
    assert versions[0]["salary_text"] == "年薪 30-40 万"
    # 详情标记有变更
    assert resp.json()["has_version_changes"] is True


def test_no_version_for_non_versioned_change(client, sample_job):
    resp = client.patch(f"/api/jobs/{sample_job['id']}", json={"status": "reviewing"})
    assert resp.status_code == 200
    assert resp.json()["versions"] == []


def test_version_snapshot_keeps_old_description(client, sample_job):
    job_id = sample_job["id"]
    old_desc = sample_job["description_raw"]
    resp = client.patch(f"/api/jobs/{job_id}", json={"description_raw": "更新后的公告全文。"})
    versions = resp.json()["versions"]
    assert len(versions) == 1
    assert versions[0]["description"] == old_desc
    change = versions[0]["changes"][0]
    assert change["field"] == "description_raw"
    assert change["old"] == old_desc


def test_no_version_when_value_unchanged(client, sample_job):
    resp = client.patch(f"/api/jobs/{sample_job['id']}", json={"salary_text": sample_job["salary_text"]})
    assert resp.status_code == 200
    assert resp.json()["versions"] == []
