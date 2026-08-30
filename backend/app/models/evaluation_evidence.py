"""Evaluation ↔ Evidence 关联表（Phase 2.1 审计性）。

记录某次评估"当时实际使用了哪些 Evidence"，使历史评估可复现：
Evidence 后续增加不会追溯改变旧评估的依据集合。
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.evidence import Evidence


class EvaluationEvidence(Base):
    __tablename__ = "evaluation_evidence"
    __table_args__ = (
        UniqueConstraint("evaluation_id", "evidence_id", name="uq_evaluation_evidence"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("job_evaluations.id"), index=True
    )
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id"), index=True)

    evaluation: Mapped["JobEvaluation"] = relationship(  # noqa: F821
        back_populates="evidence_links"
    )
    evidence: Mapped["Evidence"] = relationship()
