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


def test_reject_pi_funded_via_position_nature():
    profile = {"hard_filters": {"reject_pi_funded": True}}
    assert check_hard_filters(make_job(position_nature="pi_funded"), profile) == ["reject_pi_funded"]
    assert check_hard_filters(make_job(position_nature="tenure_track"), profile) == []


def test_reject_pi_funded_via_funding_source():
    """AcademicJobDetails.funding_source = pi 也触发（正交维度）。"""
    profile = {"hard_filters": {"reject_pi_funded": True}}
    details = SimpleNamespace(funding_source="pi")
    assert check_hard_filters(make_job(academic_details=details), profile) == ["reject_pi_funded"]


def test_reject_postdoc():
    profile = {"hard_filters": {"reject_postdoc": True}}
    assert check_hard_filters(make_job(job_category="postdoc"), profile) == ["reject_postdoc"]
    assert check_hard_filters(make_job(position_nature="postdoc"), profile) == ["reject_postdoc"]
    assert check_hard_filters(make_job(position_nature="tenure_track"), profile) == []
