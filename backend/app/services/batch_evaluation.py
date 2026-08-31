"""批量重评（Phase 7）：修改评分权重/偏好后一键重新评估全部岗位。

逐个岗位走完整 evaluate_job 编排（同一 input_snapshot 审计语义），
单个失败不中断整个任务（Collector 同款容错原则）。AI 未配置时调用方
返回 503。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.provider import AIError, LLMProvider
from app.models import Job
from app.services.evaluation import evaluate_job


def re_evaluate_all(db: Session, provider: LLMProvider) -> dict:
    job_ids = list(db.scalars(select(Job.id).order_by(Job.id)))
    succeeded: list[int] = []
    failed: list[dict] = []
    for job_id in job_ids:
        job = db.get(Job, job_id)
        try:
            evaluate_job(db, job, provider)
            succeeded.append(job_id)
        except (AIError, ValueError) as e:
            db.rollback()
            failed.append({"job_id": job_id, "error": str(e)[:300]})
        db.expunge_all()
    return {"total": len(job_ids), "succeeded": succeeded, "failed": failed}
