import json

import pytest
from pydantic import ValidationError

from app.ai.provider import AIOutputError, OpenAICompatibleProvider, parse_llm_json
from app.ai.schemas import EvaluationScores, JobEvaluationOut

VALID_EVAL = {
    "summary": "岗位与研究方向高度相关。",
    "recommendation_level": "A",
    "scores": {"fit": 85, "career_stability": 70, "region": 75, "compensation": None},
    "strengths": ["研究方向匹配"],
    "weaknesses": [],
    "risks": ["预聘制考核要求尚未找到官方文件"],
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
    assert out.recommendation_level == "A"
    assert out.scores.fit == 85
    assert out.scores.compensation is None  # 信息不足 → null，不编造


def test_evaluation_schema_rejects_bad_level():
    with pytest.raises(ValidationError):
        JobEvaluationOut.model_validate({**VALID_EVAL, "recommendation_level": "S+"})


def test_evaluation_schema_rejects_out_of_range_score():
    with pytest.raises(ValidationError):
        EvaluationScores(fit=150)


def test_scores_missing_fields_default_none():
    scores = EvaluationScores()
    assert scores.fit is None and scores.long_term is None


def test_provider_retries_once_then_raises(monkeypatch):
    provider = OpenAICompatibleProvider(api_key="k", base_url="http://x", model="m")
    calls = []

    def fake_chat(system, user):
        calls.append(system)
        return json.dumps({"recommendation_level": "Z"})  # 永远不合法

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
    assert out.recommendation_level == "A"
    assert version == "job_evaluation_v1"


def test_get_provider_none_when_not_configured(monkeypatch):
    from app.ai.provider import get_provider
    from app.core.config import Settings

    s = Settings(llm_api_key="", llm_base_url="", llm_model="")
    assert get_provider(s) is None
