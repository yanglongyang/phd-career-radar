"""Prompt 版本管理：Prompt 存放在 ai/prompts/ 目录，业务代码只引用名称，
JobEvaluation 记录 prompt_version 以便未来重新评估（第三十一节）。"""

from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"

# 名称 -> 默认版本文件名（升级时新增 *_v2.md 并在此切换）
PROMPT_REGISTRY: dict[str, str] = {
    "job_extraction": "job_extraction_v1",
    # v2：明确 reputation 只能使用 eligible Evidence（Phase 6.1.1）；
    # v1 保持原样以维护历史评估的 prompt_version 审计指向
    "job_evaluation": "job_evaluation_v2",
    # v2：AI 只输出主题叙述结论，计数改由后端确定性统计填充（Phase 6）
    "reputation_summary": "reputation_summary_v2",
}

_PROMPT_CACHE: dict[str, str] = {}


def get_prompt(name: str, version: str | None = None) -> tuple[str, str]:
    """返回 (prompt_version, prompt_text)。version 为空时使用注册表默认版本。"""
    file_stem = version or PROMPT_REGISTRY[name]
    if file_stem in _PROMPT_CACHE:
        return file_stem, _PROMPT_CACHE[file_stem]
    path = PROMPT_DIR / f"{file_stem}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    text = path.read_text(encoding="utf-8")
    _PROMPT_CACHE[file_stem] = text
    return file_stem, text
