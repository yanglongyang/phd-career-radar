from app.services.regions import get_region_score, get_region_tier


def test_preferred_city_returns_score():
    cfg = {"preferred": ["南京", "上海"]}
    assert get_region_tier("江苏", "南京", cfg) == "preferred"
    score = get_region_score("江苏", "南京", cfg)
    assert score == 90.0  # scoring.yaml region_tier_scores.preferred


def test_neutral_returns_score_not_unrated():
    cfg = {"neutral": ["合肥"]}
    assert get_region_tier("安徽", "合肥", cfg) == "neutral"
    assert get_region_score("安徽", "合肥", cfg) == 50.0


def test_unrated_city_returns_none():
    """Phase 2.1：用户没有评价过的地区 → None，不自动给 50 分替用户猜。"""
    cfg = {"preferred": ["南京"]}
    assert get_region_tier("甘肃", "兰州", cfg) == "unrated"
    assert get_region_score("甘肃", "兰州", cfg) is None


def test_no_location_returns_none():
    assert get_region_score(None, None) is None


def test_province_fallback_match():
    cfg = {"acceptable": ["江苏"]}
    assert get_region_tier("江苏", "扬州", cfg) == "acceptable"
    assert get_region_score("江苏", "扬州", cfg) == 70.0
