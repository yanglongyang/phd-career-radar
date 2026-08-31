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


def ensure_missing_columns(engine, metadata=None) -> list[str]:
    """为已有表补齐模型声明但数据库中缺失的普通列。返回新增列名列表。

    幂等：已存在的列跳过；同一引擎重复调用返回空列表。
    遇到需要复杂迁移的列（主键/外键/唯一/索引）直接报错，不做静默重建。"""
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
                if col.primary_key or col.foreign_keys or col.unique or col.index:
                    raise RuntimeError(
                        f"列 {table.name}.{col.name} 需要复杂迁移"
                        "（主键/外键/唯一/索引），请走 alembic"
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
                added.append(f"{table.name}.{col.name}")
    return added
