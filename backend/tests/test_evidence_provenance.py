from app.models import Evidence


def _create_evidence(db_session, **kwargs):
    base = dict(
        organization_id=kwargs.pop("organization_id", None),
        job_id=kwargs.pop("job_id", None),
        claim="启动经费到账较慢",
        category="startup_funding_fulfillment",
        evidence_level="C",
        source_type="zhihu",
    )
    base.update(kwargs)
    evidence = Evidence(**base)
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)
    return evidence


def test_evidence_provenance_fields(db_session, client, sample_job):
    """firsthand / 独立来源键 / 立场 / 作用域 / 转载关系可持久化。"""
    original = _create_evidence(
        db_session,
        organization_id=sample_job["organization"]["id"],
        job_id=sample_job["id"],
        source_author="知乎用户A",
        is_firsthand=True,
        independence_key="zhihu_user_a_story_2025",
        stance="negative",
        scope_level="department",
        scope_name="化学学院",
    )
    repost = _create_evidence(
        db_session,
        organization_id=sample_job["organization"]["id"],
        repost_of_evidence_id=original.id,
        source_author="转载号B",
        is_firsthand=False,  # 明确转述
        independence_key="zhihu_user_a_story_2025",  # 与原帖同源
        stance="negative",
    )
    db_session.refresh(repost)
    assert repost.repost_of_evidence_id == original.id
    assert repost.repost_of.id == original.id  # 自引用关系
    assert original.is_firsthand is True
    assert repost.is_firsthand is False
    assert original.scope_level == "department"
    assert original.scope_name == "化学学院"
    assert original.stance == "negative"
    # 同一 independence_key 标记两条证据来自同一信息源
    assert original.independence_key == repost.independence_key


def test_unknown_provenance_defaults(db_session, client, sample_job):
    evidence = _create_evidence(db_session, job_id=sample_job["id"])
    assert evidence.is_firsthand is None  # 无法判断
    assert evidence.stance == "unknown"
    assert evidence.scope_level == "unknown"


def test_deleting_job_preserves_organization_evidence(client, sample_job, db_session):
    """删除岗位不得损坏单位风评库：Evidence 保留，job_id 置空。"""
    org_id = sample_job["organization"]["id"]
    evidence = _create_evidence(db_session, organization_id=org_id, job_id=sample_job["id"])

    resp = client.delete(f"/api/jobs/{sample_job['id']}")
    assert resp.status_code == 204

    db_session.expire_all()
    row = db_session.get(Evidence, evidence.id)
    assert row is not None  # 证据没有消失
    assert row.job_id is None
    assert row.organization_id == org_id


def test_deleting_job_preserves_job_only_evidence(client, sample_job, db_session):
    """纯岗位级证据也优先保留历史（job_id 置空），不随岗位静默删除。"""
    evidence = _create_evidence(db_session, job_id=sample_job["id"], organization_id=None)
    client.delete(f"/api/jobs/{sample_job['id']}")
    db_session.expire_all()
    assert db_session.get(Evidence, evidence.id) is not None
