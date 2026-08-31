"""app/db/migrate.ensure_missing_columns：桌面版启动补列（V0.2.2）。"""

import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base

from app.db.migrate import ensure_missing_columns


def test_ensure_missing_columns_adds_only_missing(tmp_path):
    """旧表缺新列 → 补上；已存在的列不动；重复调用幂等。"""
    db_path = tmp_path / "t.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, name VARCHAR(100))"))

    Base2 = declarative_base()

    class T(Base2):
        __tablename__ = "t"
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(100))
        new_col = sa.Column(sa.Integer, default=0, nullable=False)

    added = ensure_missing_columns(engine, metadata=Base2.metadata)
    assert added == ["t.new_col"]

    with engine.connect() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(t)"))}
    assert {"id", "name", "new_col"} <= cols

    # 幂等：第二次不新增
    assert ensure_missing_columns(engine, metadata=Base2.metadata) == []


def test_ensure_missing_columns_refuses_complex_columns(tmp_path):
    """主键/外键/唯一/索引列不能靠 ADD COLUMN 补齐，必须走 alembic。"""
    db_path = tmp_path / "t.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))

    Base2 = declarative_base()

    class T(Base2):
        __tablename__ = "t"
        id = sa.Column(sa.Integer, primary_key=True)
        uid = sa.Column(sa.String(32), unique=True)

    import pytest

    with pytest.raises(RuntimeError, match="复杂迁移"):
        ensure_missing_columns(engine, metadata=Base2.metadata)
