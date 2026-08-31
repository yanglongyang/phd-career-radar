"""设置读写服务（Phase 7）：GET 读取 / PUT 写回 config/*.yaml。

原则：配置仍然以 YAML 文件为事实源（改文件即生效，无需重启）；
设置页只是"可视化编辑 YAML"的界面。PyYAML 写回会丢失注释 —— 文档与
UI 明确提示。写回前先备份原文件（.bak），失败可回滚。
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml

from app.core.config import CONFIG_DIR, load_yaml_config

_EDITABLE_FILES = ("scoring.yaml", "regions.yaml", "profile.yaml")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def read_settings() -> dict:
    """读取全部可编辑配置。"""
    return {
        name: (yaml.safe_load((CONFIG_DIR / name).read_text(encoding="utf-8")) or {})
        for name in _EDITABLE_FILES
    }


_SCORING_DIMENSIONS = {
    "fit", "career_stability", "research_resources", "region",
    "compensation", "reputation", "workload", "long_term",
}


def _validate_scoring(data: dict) -> None:
    """评分权重必须 8 维齐全、全部 numeric 且非负、合计 100。"""
    scoring = data.get("scoring")
    if not isinstance(scoring, dict):
        raise ValueError("scoring 必须是对象")
    missing = _SCORING_DIMENSIONS - set(scoring)
    if missing:
        raise ValueError(f"缺少评分维度: {sorted(missing)}（8 维必须齐全）")
    unknown = set(scoring) - _SCORING_DIMENSIONS
    if unknown:
        raise ValueError(f"未知评分维度: {sorted(unknown)}")
    total = 0.0
    for dim, value in scoring.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{dim} 必须是数字，收到 {value!r}")
        if value < 0:
            raise ValueError(f"{dim} 不能为负")
        total += float(value)
    if abs(total - 100) > 0.01:
        raise ValueError(f"评分权重合计必须为 100，当前 {total}")


def _validate_regions(data: dict) -> None:
    for tier in ("preferred", "acceptable", "neutral", "avoid"):
        values = data.get(tier) or []
        if not isinstance(values, list):
            raise ValueError(f"{tier} 必须是列表")


def _validate_hard_filters(data: dict) -> None:
    """Hard Filters：unacceptable_regions 必须列表；minimum_salary 数字或 null；
    三个排除开关必须是真正的 boolean（字符串 "false" 在 Python 里是真值，必须拒绝）。"""
    hf = data.get("hard_filters")
    if not isinstance(hf, dict):
        raise ValueError("hard_filters 必须是对象")
    regions = hf.get("unacceptable_regions", [])
    if not isinstance(regions, list):
        raise ValueError("unacceptable_regions 必须是列表")
    if not all(isinstance(r, str) for r in regions):
        raise ValueError("unacceptable_regions 的元素必须是字符串")
    if hf.get("minimum_salary") is not None:
        if not isinstance(hf["minimum_salary"], (int, float)) or isinstance(hf["minimum_salary"], bool):
            raise ValueError("minimum_salary 必须是数字或 null")
        if hf["minimum_salary"] < 0:
            raise ValueError("minimum_salary 不能为负")
    for key in ("reject_pi_funded", "reject_postdoc", "reject_high_risk_tenure_track"):
        if key in hf and not isinstance(hf[key], bool):
            raise ValueError(f"{key} 必须是 true/false，收到 {hf[key]!r}")


def update_settings(payload: dict) -> dict:
    """写回可编辑配置。备份原文件；校验失败不写任何文件。"""
    allowed = set(_EDITABLE_FILES)
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError(f"不可编辑的配置文件: {sorted(unknown)}")

    # 先整体校验，再逐个写回
    for name in allowed:
        data = payload.get(name)
        if data is None:
            continue
        if not isinstance(data, dict):
            raise ValueError(f"{name} 必须是对象")
        if name == "scoring.yaml":
            _validate_scoring(data)
        elif name == "regions.yaml":
            _validate_regions(data)
        elif name == "profile.yaml":
            _validate_hard_filters(data)

    written: dict[str, str] = {}
    for name in allowed:
        data = payload.get(name)
        if data is None:
            continue
        path: Path = CONFIG_DIR / name
        backup = CONFIG_DIR / f"{name}.bak"
        try:
            if path.exists():
                shutil.copy2(path, backup)
            path.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            written[name] = _now()
        except OSError as e:
            raise ValueError(f"写入 {name} 失败：{e}") from e
    # P0-1：配置缓存必须失效 —— 否则页面显示新值、运行时仍用旧配置
    load_yaml_config.cache_clear()
    return written
