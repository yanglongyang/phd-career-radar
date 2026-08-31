import json

import pytest
from pydantic import ValidationError

from app.ai.provider import AIOutputError, OpenAICompatibleProvider, parse_llm_json
from app.ai.schemas import (
    EvaluationScores,
    JobEvaluationOut,
    ReputationSynthesisOut,
    ReputationTopicConclusion,
)

VALID_EVAL = {
    "summary": "岗位与研究方向高度相关。",
    "scores": {"fit": 85, "career_stability": 70, "compensation": None},
    "risk_level": "medium",
    "risk_items": [
        {"type": "up_or_out", "severity": "high", "reason": "预聘制考核要求尚未找到官方文件", "evidence_ids": [12, 17]}
    ],
    "strengths": ["研究方向匹配"],
    "weaknesses": [],
    "risks": [],
    "unknowns": ["首聘周期", "国自然是否为硬性要求"],
    "questions_to_ask": ["未通过考核后的处理方式？"],
    "confidence": "medium",
}


def test_parse_llm_json_accepts_plain_and_fenced():
    assert parse_llm_json('{"a": 1}') == {"a": 1}
    assert parse_llm_json('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(AIOutputError):
        parse_llm_json("这不是 JSON")


def test_evaluation_schema_accepts_valid():
    out = JobEvaluationOut.model_validate(VALID_EVAL)
    assert out.risk_level == "medium"
    assert out.scores.fit == 85
    assert out.scores.compensation is None  # 信息不足 → null，不编造
    assert out.risk_items[0].severity == "high"
    assert out.risk_items[0].evidence_ids == [12, 17]


def test_evaluation_scores_have_no_region_field():
    """Phase 4.1.1：region 由后端 Region Engine 唯一决定，AI Schema 不再有该字段。"""
    assert "region" not in EvaluationScores.model_fields
    with pytest.raises(ValidationError):
        EvaluationScores.model_validate({"fit": 80, "region": 75})


def test_ai_schema_has_no_recommendation_or_total():
    """Phase 2.1：AI 不再拥有最终推荐等级/总分/覆盖度的决定权。"""
    assert "recommendation_level" not in JobEvaluationOut.model_fields
    assert "total_score" not in JobEvaluationOut.model_fields
    assert "score_coverage" not in JobEvaluationOut.model_fields


def test_evaluation_schema_rejects_bad_risk_level():
    with pytest.raises(ValidationError):
        JobEvaluationOut.model_validate({**VALID_EVAL, "risk_level": "extreme"})


def test_evaluation_schema_rejects_out_of_range_score():
    with pytest.raises(ValidationError):
        EvaluationScores(fit=150)


def test_scores_missing_fields_default_none():
    scores = EvaluationScores()
    assert scores.fit is None and scores.long_term is None


def test_reputation_synthesis_strict_schema():
    """Phase 6：AI 风评输出只含主题叙述结论 —— 计数由后端确定性统计填充，
    模型不得输出任何数字字段。"""
    synthesis = ReputationSynthesisOut.model_validate(
        {
            "topics": [
                {"topic": "assessment_pressure", "conclusion": "统计显示考核压力反馈较多。"}
            ]
        }
    )
    assert synthesis.topics[0].topic == "assessment_pressure"
    assert not hasattr(synthesis.topics[0], "independent_sources")
    # Phase 6.1：AI 不得输出 confidence/overall_note —— 置信度由确定性规则唯一决定
    assert not hasattr(synthesis, "confidence")
    assert not hasattr(synthesis, "overall_note")
    with pytest.raises(ValidationError):
        ReputationSynthesisOut.model_validate(
            {"topics": [], "confidence": "high"}
        )
    # 非法主题拒绝
    with pytest.raises(ValidationError):
        ReputationSynthesisOut.model_validate(
            {"topics": [{"topic": "whatever", "conclusion": "x"}]}
        )
    # 模型擅自输出计数字段 → extra=forbid 拒绝
    with pytest.raises(ValidationError):
        ReputationTopicConclusion.model_validate(
            {"topic": "other", "conclusion": "x", "independent_sources": 3}
        )


def test_reputation_summary_rejects_arbitrary_topics():
    with pytest.raises(ValidationError):
        ReputationSynthesisOut.model_validate(
            {"topics": [{"whatever": 123}], "overall_note": "", "confidence": "low"}
        )


def test_provider_retries_once_then_raises(monkeypatch):
    provider = OpenAICompatibleProvider(api_key="k", base_url="http://x", model="m")
    calls = []

    def fake_chat(system, user):
        calls.append(system)
        return json.dumps({"risk_level": "extreme"})  # 永远不合法

    monkeypatch.setattr(provider, "_chat", fake_chat)
    with pytest.raises(AIOutputError) as exc:
        provider.evaluate_job({"job": {}})
    assert len(calls) == 2  # 自动重试一次
    assert "仍不合法" in str(exc.value)


def test_provider_success_after_retry(monkeypatch):
    provider = OpenAICompatibleProvider(api_key="k", base_url="http://x", model="m")
    state = {"n": 0}

    def fake_chat(system, user):
        state["n"] += 1
        if state["n"] == 1:
            return "抱歉，我无法输出 JSON。"  # 第一次失败
        return json.dumps(VALID_EVAL, ensure_ascii=False)

    monkeypatch.setattr(provider, "_chat", fake_chat)
    out, version = provider.evaluate_job({"job": {}})
    assert state["n"] == 2
    assert out.risk_level == "medium"
    assert version == "job_evaluation_v2"


def test_get_provider_none_when_not_configured():
    from app.ai.provider import get_provider
    from app.core.config import Settings

    s = Settings(llm_api_key="", llm_base_url="", llm_model="")
    assert get_provider(s) is None


def test_evaluation_required_fields_have_no_defaults():
    """Phase 4.1：risk_level / confidence / scores 必填 —— 模型漏字段触发重试，
    而不是被 Pydantic 静默补成 medium（"没输出风险" != "明确判断中风险"）。"""
    for missing in ("risk_level", "confidence", "scores"):
        bad = {k: v for k, v in VALID_EVAL.items() if k != missing}
        with pytest.raises(ValidationError):
            JobEvaluationOut.model_validate(bad)
