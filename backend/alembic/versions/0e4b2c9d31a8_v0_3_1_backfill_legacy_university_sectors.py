"""v0.3.1 backfill legacy university sectors

V0.3 迁移把历史行统一回填为 other；这里按"发现时的来源"把已知高校来源的
旧记录一次性修正为 university。映射硬编码在迁移中（快照），不读取
sources.yaml —— 未来修改配置不回溯历史语义。

Revision ID: 0e4b2c9d31a8
Revises: 9834a5845c71
Create Date: 2026-09-01

"""
import sqlalchemy as sa

from alembic import op

revision = '0e4b2c9d31a8'
down_revision = '9834a5845c71'
branch_labels = None
depends_on = None

# 与 app/db/migrate.py 的 LEGACY_SECTOR_BACKFILL 保持一致（同一快照）
_KNOWN_UNIVERSITY_SOURCES = (
    'sjtu_postdoc', 'sjtu_research', 'hust_faculty', 'pku_rczp', 'fudan_hr',
)


def upgrade() -> None:
    # 硬编码常量内联（不读 sources.yaml，未来改配置不回溯）
    ids = ", ".join(f"'{s}'" for s in _KNOWN_UNIVERSITY_SOURCES)
    op.execute(
        sa.text(
            "UPDATE discovered_jobs SET sector='university' "
            f"WHERE sector='other' AND source_id IN ({ids})"
        )
    )


def downgrade() -> None:
    # 一次性数据修正，降级不回溯（保持现状）
    pass
