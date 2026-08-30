import json

import pytest
from pydantic import ValidationError

from app.ai.provider import AIOutputError, OpenAICompatibleProvider, parse_llm_json
from app.ai.schemas import (
    EvaluationScores,
    JobEvaluationOut,
    ReputationSummaryOut,
    ReputationTopicOut,
)

VALID_EVAL = {
    "summary": "岗位与研究方向高度相关。",
    "scores": {"fit": 85, "career_stability": 70, "region": 75, "compensation": None},
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


def test_reputation_topic_strict_schema():
    """Phase 2.1：风评聚合不再接受 list[dict] 的宽松结构。"""
    topic = ReputationTopicOut.model_validate(
        {
            "topic": "assessment_pressure",
            "positive_sources": 1,
            "negative_sources": 2,
            "independent_sources": 3,
            "evidence_levels": ["B", "C"],
            "time_start": "2024-03",
            "time_end": "2026-05",
            "conclusion": "存在较多关于考核压力的负面反馈。",
        }
    )
    assert topic.independent_sources == 3
    with pytest.raises(ValidationError):
        ReputationTopicOut.model_validate({**topic.model_dump(), "topic": "whatever_topic"})
    with pytest.raises(ValidationError):
        ReputationTopicOut.model_validate({**topic.model_dump(), "negative_sources": -1})


def test_reputation_summary_rejects_arbitrary_topics():
    with pytest.raises(ValidationError):
        ReputationSummaryOut.model_validate(
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
    assert version == "job_evaluation_v1"


def test_get_provider_none_when_not_configured():
    from app.ai.provider import get_provider
    from app.core.config import Settings

    s = Settings(llm_api_key="", llm_base_url="", llm_model="")
    assert get_provider(s) is None
