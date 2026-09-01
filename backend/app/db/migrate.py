"""启动时轻量结构补齐（桌面版升级路径）。

开发/CI 用 alembic 管理结构；但 exe 分发的桌面版在用户已有数据库上
不会自动执行 alembic，而 create_all 只建缺失表、不补缺失列。
这里对新版本新增的普通列（非主键/外键/唯一/索引）执行 ADD COLUMN，
保证旧库打开新 exe 不报 no such column。

约束：SQLite 的 ALTER TABLE ADD COLUMN 只支持简单类型列，
主键/外键/唯一/索引列的结构变更仍然必须走 alembic 全量迁移。
"""

from __future__ import annotations

from sqlalchemy import inspect, text

# V0.3.1 一次性数据修正快照：V0.3 迁移把历史行统一回填为 other，
# 这里按"发现时的来源"把已知高校来源的旧记录修正为 university。
# 与迁移 0e4b2c9d31a8 的映射保持一致；硬编码，不读取 sources.yaml ——
# 未来修改配置不回溯历史语义（sector 在发现时冻结）。
LEGACY_SECTOR_BACKFILL: dict[str, str] = {
    "sjtu_postdoc": "university",
    "sjtu_research": "university",
    "hust_faculty": "university",
    "pku_rczp": "university",
    "fudan_hr": "university",
}


def ensure_missing_columns(engine, metadata=None) -> list[str]:
    """为已有表补齐模型声明但数据库中缺失的普通列。返回新增列名列表。

    幂等：已存在的列跳过；同一引擎重复调用返回空列表。
    支持普通索引列（ADD COLUMN 后补 CREATE INDEX）；主键/外键/唯一列
    需要重建表，直接报错，不做静默重建（必须走 alembic）。"""
    from app.db.base import Base

    metadata = metadata or Base.metadata
    dialect = engine.dialect
    added: list[str] = []
    with engine.begin() as conn:
        insp = inspect(conn)
        tables = set(insp.get_table_names())
        for table in metadata.sorted_tables:
            if table.name not in tables:
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                if col.primary_key or col.foreign_keys or col.unique:
                    raise RuntimeError(
                        f"列 {table.name}.{col.name} 需要复杂迁移"
                        "（主键/外键/唯一），请走 alembic"
                    )
                ddl = (
                    f"ALTER TABLE {table.name} ADD COLUMN {col.name} "
                    f"{col.type.compile(dialect=dialect)}"
                )
                # NOT NULL 列必须有默认值（SQLite 限制）；优先用模型 scalar default
                default = None
                if col.default is not None and col.default.is_scalar:
                    default = col.default.arg
                elif not col.nullable:
                    default = 0
                if default is not None:
                    ddl += f" DEFAULT {default}"
                conn.execute(text(ddl))
                if col.index:
                    # SQLite 的 ADD COLUMN 不能直接带索引 → 补列后单独建索引
                    conn.execute(text(
                        f"CREATE INDEX IF NOT EXISTS ix_{table.name}_{col.name} "
                        f"ON {table.name} ({col.name})"
                    ))
                added.append(f"{table.name}.{col.name}")
    return added


def backfill_legacy_sectors(engine) -> int:
    """一次性数据修正（桌面升级路径，幂等）：V0.3 迁移把历史行回填为 other，
    这里按发现时的来源把已知高校来源的旧记录修正为 university。

    只更新 sector='other' 的行（不覆盖任何已有值）；映射硬编码快照，
    不读取 sources.yaml。返回更新的行数。"""
    if "discovered_jobs" not in inspect(engine).get_table_names():
        return 0
    updated = 0
    with engine.begin() as conn:
        for source_id, sector in LEGACY_SECTOR_BACKFILL.items():
            result = conn.execute(
                text(
                    "UPDATE discovered_jobs SET sector=:s "
                    "WHERE sector='other' AND source_id=:id"
                ),
                {"s": sector, "id": source_id},
            )
            updated += result.rowcount or 0
    return updated
