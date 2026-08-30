"""配置快照哈希（Phase 2.1 审计性）。

对任意配置 dict 生成确定性哈希：key 排序、UTF-8、紧凑分隔符、SHA-256。
同一内容无论 key 顺序如何，hash 必须相同。
"""

import hashlib
import json


def stable_json_hash(data: dict | list | None) -> str:
    if data is None:
        data = {}
    serialized = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    """对原始文本计算 SHA-256（UTF-8），用于导入审计的 source_text_hash。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
