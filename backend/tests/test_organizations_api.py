def test_organization_crud_and_delete_guard(client, sample_job):
    orgs = client.get("/api/organizations").json()
    assert len(orgs) == 1
    org = orgs[0]
    assert org["name"] == "示例大学"
    assert org["job_count"] == 1

    # 有岗位的单位不能删除
    resp = client.delete(f"/api/organizations/{org['id']}")
    assert resp.status_code == 409

    # 新建 + 更新 + 删除空单位
    created = client.post(
        "/api/organizations",
        json={"name": "某研究院", "organization_type": "research_institute", "city": "北京"},
    )
    assert created.status_code == 201
    org_id = created.json()["id"]

    updated = client.patch(f"/api/organizations/{org_id}", json={"province": "北京"})
    assert updated.json()["province"] == "北京"

    assert client.delete(f"/api/organizations/{org_id}").status_code == 204

    # 名称搜索
    assert client.get("/api/organizations", params={"q": "示例"}).json()[0]["id"] == org["id"]
