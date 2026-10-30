"""Historical notices, regional coverage and collection audit.

Revision ID: 5c8d3a0e2f14
Revises: 0e4b2c9d31a8
"""

import sqlalchemy as sa

from alembic import op

revision = "5c8d3a0e2f14"
down_revision = "0e4b2c9d31a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Desktop startup may have already added these simple columns. Alembic
    # must remain usable afterwards without duplicate-column failures.
    additions = {
        "collector_runs": [
            sa.Column("mode", sa.String(16), server_default="recent", nullable=False),
            sa.Column("history_years", sa.Integer(), nullable=True),
            sa.Column("province", sa.String(32), nullable=True),
        ],
        "collector_run_items": [sa.Column("warning_count", sa.Integer(), server_default="0", nullable=False)],
        "discovered_jobs": [
            sa.Column("url_identity", sa.String(1024), nullable=True),
            sa.Column("announcement_year", sa.Integer(), nullable=True),
            sa.Column("province", sa.String(32), nullable=True),
            sa.Column("requirements_summary", sa.Text(), nullable=True),
            sa.Column("benefits_summary", sa.Text(), nullable=True),
        ],
    }
    inspector = sa.inspect(op.get_bind())
    for table, columns in additions.items():
        existing = {c["name"] for c in inspector.get_columns(table)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table, column)
    indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("discovered_jobs")}
    for column in ("announcement_year", "province", "url_identity"):
        name = f"ix_discovered_jobs_{column}"
        if name not in indexes:
            op.create_index(name, "discovered_jobs", [column])


def downgrade() -> None:
    for column in ("announcement_year", "province", "url_identity"):
        op.drop_index(f"ix_discovered_jobs_{column}", table_name="discovered_jobs")
    for table, columns in {
        "discovered_jobs": [
            "benefits_summary", "requirements_summary", "province", "announcement_year", "url_identity",
        ],
        "collector_run_items": ["warning_count"],
        "collector_runs": ["province", "history_years", "mode"],
    }.items():
        for column in columns:
            op.drop_column(table, column)
