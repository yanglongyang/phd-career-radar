"""FastAPI 依赖。"""

from app.ai.provider import LLMProvider, get_provider


def get_ai_provider() -> LLMProvider | None:
    """AI Provider 依赖：未配置时返回 None，路由显式报 503，不伪造结果。
    测试通过 dependency_overrides 注入 FakeProvider。"""
    return get_provider()
