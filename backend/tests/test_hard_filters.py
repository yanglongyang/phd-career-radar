from types import SimpleNamespace

from app.services.hard_filters import check_hard_filters


def make_job(**kwargs):
    base = dict(
        city="南京", province="江苏", position_nature="tenure_track",
        job_category="university_research", salary_max=None, salary_min=None,
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


def test_minimum_salary_only_triggers_when_known():
    profile = {"hard_filters": {"minimum_salary": 30}}
    # 薪资未知 → 不触发过滤（信息缺口，不是违规）
    assert check_hard_filters(make_job(salary_max=None), profile) == []
    assert check_hard_filters(make_job(salary_max=25), profile) == ["minimum_salary"]
    assert check_hard_filters(make_job(salary_max=35), profile) == []


def test_reject_pi_funded_and_postdoc():
    profile = {"hard_filters": {"reject_pi_funded": True, "reject_postdoc": True}}
    assert check_hard_filters(make_job(position_nature="pi_funded"), profile) == ["reject_pi_funded"]
    assert check_hard_filters(make_job(job_category="postdoc"), profile) == ["reject_postdoc"]
    assert check_hard_filters(make_job(position_nature="postdoc"), profile) == ["reject_postdoc"]
    assert check_hard_filters(make_job(position_nature="tenure_track"), profile) == []
