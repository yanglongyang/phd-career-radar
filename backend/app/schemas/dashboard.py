"""Dashboard 汇总输出。"""

from pydantic import BaseModel

from app.schemas.job import JobListItem


class DashboardCounts(BaseModel):
    new_today: int = 0
    to_review: int = 0      # 待查看（new + reviewing）
    high_match: int = 0     # 高匹配（推荐等级 S/A）
    focus: int = 0          # 重点关注（shortlisted）
    preparing: int = 0      # 准备投递
    applied: int = 0        # 已投递
    interviewing: int = 0   # 面试中
    offer: int = 0


class DashboardOut(BaseModel):
    counts: DashboardCounts
    top_jobs: list[JobListItem] = []
