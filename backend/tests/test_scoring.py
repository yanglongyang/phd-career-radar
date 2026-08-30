from app.services.scoring import compute_total, recommend_level

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


def test_risk_and_confidence_caps():
    cfg = {
        "thresholds": {"S": 85, "A": 75, "B": 65, "C": 50},
        "risk_cap": {"critical": "D", "high": "C"},
        "confidence_cap": {"low": "B"},
    }
    # 90 分本应是 S，但高风险封顶到 C
    assert recommend_level(90, risk_level="high", cfg=cfg) == "C"
    assert recommend_level(90, risk_level="critical", cfg=cfg) == "D"
    # 低可信度封顶到 B
    assert recommend_level(90, confidence="low", cfg=cfg) == "B"
    # 封顶取更严者
    assert recommend_level(90, risk_level="high", confidence="low", cfg=cfg) == "C"
