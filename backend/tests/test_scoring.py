from app.services.scoring import compute_coverage, compute_total, recommend_level

WEIGHTS = {
    "fit": 20,
    "career_stability": 15,
    "research_resources": 15,
    "region": 15,
    "compensation": 10,
    "reputation": 10,
    "workload": 5,
    "long_term": 10,
}


def test_compute_total_weighted_average():
    scores = {"fit": 90, "region": 60}
    # (90*20 + 60*15) / 35 = 77.1
    assert compute_total(scores, WEIGHTS) == 77.1


def test_compute_total_renormalizes_when_info_missing():
    """信息不足的维度不参与计算 —— 不因信息缺失人为压分。"""
    scores = {"fit": 80, "career_stability": None}
    assert compute_total(scores, WEIGHTS) == 80.0


def test_compute_total_none_when_no_scores():
    assert compute_total({}, WEIGHTS) is None
    assert compute_total({"fit": None}, WEIGHTS) is None


def test_compute_coverage_partial():
    """fit(20) + region(15) 已评分 → coverage = 35。"""
    scores = {"fit": 90, "region": 80, "career_stability": None, "compensation": None}
    assert compute_coverage(scores, WEIGHTS) == 35.0


def test_compute_coverage_full():
    all_scores = {k: 60 for k in WEIGHTS}
    assert compute_coverage(all_scores, WEIGHTS) == 100.0


def test_compute_coverage_zero_when_all_null():
    assert compute_coverage({}, WEIGHTS) == 0.0
    assert compute_coverage({k: None for k in WEIGHTS}, WEIGHTS) == 0.0


def test_recommend_level_by_thresholds():
    cfg = {"thresholds": {"S": 85, "A": 75, "B": 65, "C": 50}}
    assert recommend_level(92, cfg=cfg) == "S"
    assert recommend_level(80, cfg=cfg) == "A"
    assert recommend_level(70, cfg=cfg) == "B"
    assert recommend_level(55, cfg=cfg) == "C"
    assert recommend_level(30, cfg=cfg) == "D"
    assert recommend_level(None, cfg=cfg) is None


def test_hard_filter_triggers_x():
    cfg = {"thresholds": {"S": 85, "A": 75, "B": 65, "C": 50}}
    assert recommend_level(92, hard_filter_hits=["unacceptable_regions"], cfg=cfg) == "X"


def test_risk_caps():
    cfg = {
        "thresholds": {"S": 85, "A": 75, "B": 65, "C": 50},
        "risk_cap": {"critical": "D", "high": "C"},
    }
    # 90 分本应是 S，但高风险封顶到 C
    assert recommend_level(90, risk_level="high", cfg=cfg) == "C"
    assert recommend_level(90, risk_level="critical", cfg=cfg) == "D"


def test_low_confidence_does_not_lower_recommendation():
    """信息不足 ≠ 岗位价值低：low confidence 不得把 S/A 降到 B（Phase 2.1 移除默认封顶）。"""
    cfg = {
        "thresholds": {"S": 85, "A": 75, "B": 65, "C": 50},
        "risk_cap": {"critical": "D", "high": "C"},
        "confidence_cap": {},  # 默认关闭
    }
    assert recommend_level(90, confidence="low", cfg=cfg) == "S"
    assert recommend_level(90, risk_level="medium", confidence="low", cfg=cfg) == "S"
    assert recommend_level(80, confidence="low", cfg=cfg) == "A"


def test_high_score_with_low_coverage_is_still_high():
    """只评了 fit=95：provisional score = 95，但 coverage 只有 20 —— 分数不降，
    覆盖度必须暴露信息不足（虚假精度问题由 coverage 解决，不靠压分）。"""
    scores = {"fit": 95}
    assert compute_total(scores, WEIGHTS) == 95.0
    assert compute_coverage(scores, WEIGHTS) == 20.0
