from types import SimpleNamespace

from app.services.hard_filters import check_hard_filters


def make_job(**kwargs):
    base = dict(
        city="南京", province="江苏", position_nature="unknown",
        job_category="university_research",
        salary_max=None, salary_min=None,
        salary_currency=None, salary_period=None,
        guaranteed_salary_max=None, guaranteed_salary_min=None,
        academic_details=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_no_filters_configured_no_trigger():
    profile = {"hard_filters": {}}
    assert check_hard_filters(make_job(), profile) == []


def test_unacceptable_region_match_city_or_province():
    profile = {"hard_filters": {"unacceptable_regions": ["某城"]}}
    assert check_hard_filters(make_job(city="某城"), profile) == ["unacceptable_regions"]
    assert check_hard_filters(make_job(province="某城"), profile) == ["unacceptable_regions"]
    assert check_hard_filters(make_job(city="南京", province="江苏"), profile) == []


def test_salary_filter_requires_normalized_fields():
    """明确 CNY 年薪且 guaranteed_salary_max 低于下限 → 可过滤。"""
    profile = {"hard_filters": {"minimum_salary": 30}}
    job = make_job(salary_currency="CNY", salary_period="year", guaranteed_salary_max=25)
    assert check_hard_filters(job, profile) == ["minimum_salary"]


def test_salary_filter_not_triggered_when_period_unknown():
    """period 未知 → 不触发，进入 unknowns/待确认（不得猜单位）。"""
    profile = {"hard_filters": {"minimum_salary": 30}}
    job = make_job(salary_currency="CNY", salary_period=None, guaranteed_salary_max=25)
    assert check_hard_filters(job, profile) == []


def test_salary_filter_not_triggered_when_currency_unknown():
    profile = {"hard_filters": {"minimum_salary": 30}}
    job = make_job(salary_currency=None, salary_period="year", guaranteed_salary_max=25)
    assert check_hard_filters(job, profile) == []


def test_salary_filter_ignores_legacy_and_advertised_max():
    """legacy salary_max / advertised_total_max 含绩效口径，不得用于硬性过滤。"""
    profile = {"hard_filters": {"minimum_salary": 30}}
    job = make_job(salary_max=25, advertised_total_max=25)  # 无 currency/period/guaranteed
    assert check_hard_filters(job, profile) == []


def test_salary_filter_ok_when_guaranteed_above_minimum():
    profile = {"hard_filters": {"minimum_salary": 30}}
    job = make_job(salary_currency="CNY", salary_period="year", guaranteed_salary_max=35)
    assert check_hard_filters(job, profile) == []


def test_reject_pi_funded_via_funding_source_only():
    """Phase 2.1.1：legacy position_nature 不再参与判断，只看正交的 funding_source。"""
    profile = {"hard_filters": {"reject_pi_funded": True}}
    assert check_hard_filters(
        make_job(academic_details=SimpleNamespace(funding_source="pi")), profile
    ) == ["reject_pi_funded"]
    assert check_hard_filters(make_job(), profile) == []
    # legacy 字段即使残留 pi_funded 旧值也不再触发
    assert check_hard_filters(
        make_job(position_nature="pi_funded"), profile
    ) == []


def test_reject_postdoc_only_by_category():
    profile = {"hard_filters": {"reject_postdoc": True}}
    assert check_hard_filters(make_job(job_category="postdoc"), profile) == ["reject_postdoc"]
    assert check_hard_filters(make_job(job_category="university_faculty"), profile) == []


def test_reject_high_risk_tenure_track_executes():
    """Phase 2.1.1：该开关不再是死配置 —— 评估时具备 tenure 状态与有效风险后真正生效。"""
    profile = {"hard_filters": {"reject_high_risk_tenure_track": True}}
    track = SimpleNamespace(tenure_status="tenure_track")
    tenured = SimpleNamespace(tenure_status="tenured")

    assert check_hard_filters(
        make_job(academic_details=track), profile, risk_level="high"
    ) == ["reject_high_risk_tenure_track"]
    assert check_hard_filters(
        make_job(academic_details=track), profile, risk_level="critical"
    ) == ["reject_high_risk_tenure_track"]
    # 风险不足、非预聘、未填详情、开关关闭 → 都不触发
    assert check_hard_filters(make_job(academic_details=track), profile, risk_level="medium") == []
    assert check_hard_filters(make_job(academic_details=tenured), profile, risk_level="high") == []
    assert check_hard_filters(make_job(), profile, risk_level="high") == []
    assert check_hard_filters(make_job(academic_details=track), {"hard_filters": {}}, risk_level="high") == []
