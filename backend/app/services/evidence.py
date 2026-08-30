"""Evidence 事实资产完整性（Phase 6.1）：转载链校验。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Evidence


class RepostChainError(ValueError):
    """转载关系非法（目标不存在/自身/循环/跨单位）。"""


def validate_repost_chain(
    db: Session, *, evidence_id: int | None, repost_of: int | None, organization_id: int | None
) -> None:
    """校验 repost_of_evidence_id 指向的转载关系：
    - 目标必须存在（否则 canonical 追根断链）；
    - 不得指向自身；
    - 不得构成循环（沿链回溯发现自身）；
    - 不得跨单位（canonical 追根只在单位全量证据内进行）。"""
    if repost_of is None:
        return
    if evidence_id is not None and repost_of == evidence_id:
        raise RepostChainError("证据不能转载自身")
    parent = db.get(Evidence, repost_of)
    if parent is None:
        raise RepostChainError(f"转载目标不存在: {repost_of}")
    if organization_id is not None and parent.organization_id != organization_id:
        raise RepostChainError("转载目标属于其他单位，禁止跨单位转载")
    # 沿链回溯检查循环
    seen: set[int] = set()
    current = parent
    while current is not None:
        if evidence_id is not None and current.id == evidence_id:
            raise RepostChainError("转载关系构成循环")
        if current.id in seen:
            break  # 既有数据已有环，不再深入（当前写入仍被上方检查保护）
        seen.add(current.id)
        if current.repost_of_evidence_id is None:
            break
        nxt = db.get(Evidence, current.repost_of_evidence_id)
        if nxt is None:
            break
        current = nxt
