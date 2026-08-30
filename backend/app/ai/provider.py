"""LLM Provider 抽象（第三节）：项目不绑定任何模型 API。
当前实现 OpenAI-compatible（环境变量 LLM_PROVIDER / LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）。
AI 未配置时 get_provider() 返回 None，调用方必须显式提示用户，禁止伪造结果。

AI 输出统一走 `_complete_json`：Pydantic 校验失败自动重试一次，仍失败抛 AIOutputError。
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

import httpx
from pydantic import ValidationError

from app.ai.prompts import get_prompt
from app.ai.schemas import JobEvaluationOut, JobExtractionOut, ReputationSummaryOut
from app.core.config import Settings, get_settings

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class AIError(Exception):
    """AI 调用失败（网络/HTTP/配置）。"""


class AIConfigError(AIError):
    """AI 未配置或配置不完整。"""


class AIOutputError(AIError):
    """AI 输出经过一次重试仍无法通过校验。"""


def strip_code_fences(text: str) -> str:
    return _JSON_FENCE.sub("", text.strip()).strip()


def parse_llm_json(content: str) -> dict:
    try:
        data = json.loads(strip_code_fences(content))
    except json.JSONDecodeError as e:
        raise AIOutputError(f"AI 输出不是合法 JSON：{e}") from e
    if not isinstance(data, dict):
        raise AIOutputError("AI 输出必须是 JSON 对象")
    return data


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def extract_job(self, jd_text: str) -> tuple[JobExtractionOut, str]:
        """返回 (结构化岗位, prompt_version)。"""

    @abstractmethod
    def evaluate_job(self, context: dict) -> tuple[JobEvaluationOut, str]:
        """返回 (结构化评估, prompt_version)。"""

    @abstractmethod
    def summarize_reputation(self, evidence: list[dict]) -> tuple[ReputationSummaryOut, str]:
        """返回 (风评聚合, prompt_version)。"""


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float = 90.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _chat(self, system: str, user: str) -> str:
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.2,
                },
                timeout=self.timeout,
            )
        except httpx.HTTPError as e:
            raise AIError(f"AI 请求失败：{e}") from e
        if resp.status_code >= 400:
            raise AIError(f"AI 返回 HTTP {resp.status_code}：{resp.text[:300]}")
        try:
            return resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            raise AIError(f"AI 响应格式异常：{e}") from e

    def _complete_json(self, prompt_name: str, payload: dict, schema_cls):
        prompt_version, template = get_prompt(prompt_name)
        system_base = template + (
            "\n\n重要：只输出一个合法 JSON 对象，不要输出解释文字或 Markdown 代码块标记。"
            "缺失信息输出 null，禁止编造。"
        )
        user_content = json.dumps(payload, ensure_ascii=False)
        last_error = ""
        for attempt in range(2):
            system = system_base
            if attempt > 0:
                system += f"\n\n上一次输出不合法：{last_error} 请修正后严格重新输出。"
            content = self._chat(system, user_content)
            try:
                data = parse_llm_json(content)
                return schema_cls.model_validate(data), prompt_version
            except (AIOutputError, ValidationError) as e:
                last_error = str(e)[:500]
        raise AIOutputError(f"AI 输出重试后仍不合法：{last_error}")

    def extract_job(self, jd_text: str) -> tuple[JobExtractionOut, str]:
        out, version = self._complete_json(
            "job_extraction", {"jd_text": jd_text}, JobExtractionOut
        )
        return out, version

    def evaluate_job(self, context: dict) -> tuple[JobEvaluationOut, str]:
        return self._complete_json("job_evaluation", context, JobEvaluationOut)

    def summarize_reputation(self, evidence: list[dict]) -> tuple[ReputationSummaryOut, str]:
        return self._complete_json("reputation_summary", {"evidence": evidence}, ReputationSummaryOut)


def get_provider(settings: Settings | None = None) -> LLMProvider | None:
    s = settings or get_settings()
    if not (s.llm_api_key and s.llm_base_url and s.llm_model):
        return None
    return OpenAICompatibleProvider(
        api_key=s.llm_api_key, base_url=s.llm_base_url, model=s.llm_model
    )
