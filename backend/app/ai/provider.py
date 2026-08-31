"""LLM Provider 抽象（第三节）：项目不绑定任何模型 API。
当前实现 OpenAI-compatible（环境变量 LLM_PROVIDER / LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）。
AI 未配置时 get_provider() 返回 None，调用方必须显式提示用户，禁止伪造结果。

AI 输出统一走 `_complete_json`：Pydantic 校验失败自动重试一次，仍失败抛 AIOutputError。
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod

import httpx
from pydantic import ValidationError

from app.ai.prompts import get_prompt
from app.ai.schemas import (
    JobEvaluationOut,
    JobExtractionOut,
    ReputationSynthesisOut,
)
from app.core.config import Settings, get_settings
from app.core.endpoints import normalize_base_url, validate_llm_base_url

logger = logging.getLogger(__name__)

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

# 允许出现在 AI 错误提示里的受控字段（type / request-id），其余一律不回显
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")


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
    def summarize_reputation(self, context: dict) -> tuple[ReputationSynthesisOut, str]:
        """返回 (AI 主题综合结论, prompt_version)。计数由后端统计填充。"""


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
            raise AIError(_http_error_message(resp))
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

    def summarize_reputation(self, context: dict) -> tuple[ReputationSynthesisOut, str]:
        return self._complete_json("reputation_summary", context, ReputationSynthesisOut)


def get_provider(settings: Settings | None = None) -> LLMProvider | None:
    """构造 Provider；配置缺失、接口地址不合规、或 endpoint 与密钥绑定不一致
    时返回 None（AI 显式禁用，路由报 503，不伪造结果）。

    V0.2.4 credential destination integrity：密钥文件里保存的是用户确认过的
    endpoint；当前 .env 的 LLM_BASE_URL 与之一致才允许发送 Key ——
    .env 被篡改成另一个 host 时拒绝请求，要求用户在启动器重新确认。"""
    s = settings or get_settings()
    if not (s.llm_api_key and s.llm_base_url and s.llm_model):
        return None
    url_err = validate_llm_base_url(s.llm_base_url)
    if url_err:
        logger.warning("AI 禁用：接口地址不合规 —— %s", url_err)
        return None
    from app.core.config import DATA_DIR
    from app.core.secrets import load_secret, secret_path

    payload = load_secret(secret_path(DATA_DIR))
    if payload:
        if not payload.get("base_url"):
            # 旧格式密钥无绑定信息：保守拒绝，要求重新确认（不发送 Key）
            logger.warning(
                "AI 禁用：密钥未绑定接口地址（旧格式），请在启动器「API 设置」重新保存"
            )
            return None
        if normalize_base_url(payload["base_url"]) != normalize_base_url(s.llm_base_url):
            logger.warning(
                "AI 禁用：LLM_BASE_URL 与密钥绑定的接口地址不一致"
                "（绑定 %r，当前 %r）——请在启动器「API 设置」重新确认",
                payload["base_url"], s.llm_base_url,
            )
            return None
    return OpenAICompatibleProvider(
        api_key=s.llm_api_key, base_url=s.llm_base_url, model=s.llm_model
    )


def _http_error_message(resp) -> str:
    """构造 AI HTTP 错误提示：不回显远端错误正文（第三方/恶意 provider 可能
    把敏感内容放进 body），只保留状态码 + 受控字段（error.type、x-request-id）。"""
    msg = f"AI 返回 HTTP {resp.status_code}"
    try:
        data = resp.json()
    except ValueError:
        data = None
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        etype = data["error"].get("type")
        if isinstance(etype, str) and _SAFE_TOKEN.match(etype):
            msg += f"（{etype}）"
    req_id = resp.headers.get("x-request-id", "")
    if req_id and _SAFE_TOKEN.match(req_id):
        msg += f" request-id={req_id}"
    return msg
