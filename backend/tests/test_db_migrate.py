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


# ---------- V0.3 迁移回归：真实 alembic 升级路径（旧库 → head） ----------

def _upgrade_to(cfg, revision: str) -> None:
    from alembic import command

    command.upgrade(cfg, revision)


def test_migration_v03_sector_backfills_other(tmp_path, monkeypatch):
    """旧库（无 sector 列）已有历史行 → upgrade head →
    旧行 sector='other'（不产生 NULL）、索引存在；新行默认 other。"""
    import sqlite3

    from alembic.config import Config

    from app.core import config as config_mod

    db_path = tmp_path / "mig_v03.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    config_mod.get_settings.cache_clear()
    try:
        cfg = Config(str(config_mod.PROJECT_ROOT / "backend" / "alembic.ini"))
        cfg.set_main_option(
            "script_location", str(config_mod.PROJECT_ROOT / "backend" / "alembic")
        )
        # 1) 升级到 V0.2.2 旧版本（无 sector 列）
        _upgrade_to(cfg, "87c3300ba3ba")
        # 2) 写入旧 schema 的历史数据（模拟用户已有数据库）
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO discovered_jobs (source_id, source_name, source_url, status,"
            " discovered_at, last_seen_at) VALUES ('s1','S1','https://x/1','new',"
            " '2026-01-01 00:00:00','2026-01-01 00:00:00')"
        )
        conn.execute(
            "INSERT INTO collector_run_items (run_id, source_id, source_name, status,"
            " started_at, fetched_count, new_count, duplicate_count,"
            " possible_duplicate_count, filtered_count)"
            " VALUES (1,'s1','S1','success','2026-01-01 00:00:00',0,0,0,0,0)"
        )
        conn.commit()
        conn.close()
        # 3) 升级到 head（V0.3 加 sector 列）
        _upgrade_to(cfg, "head")
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT sector FROM discovered_jobs WHERE source_id='s1'"
        ).fetchone()
        assert row is not None and row[0] == "other"      # 历史行回填 other，非 NULL
        row2 = conn.execute(
            "SELECT sector FROM collector_run_items WHERE source_id='s1'"
        ).fetchone()
        assert row2 is not None and row2[0] == "other"
        indexes = [str(i[1]) for i in conn.execute("PRAGMA index_list(discovered_jobs)")]
        assert any("sector" in name for name in indexes)  # 索引存在
        conn.close()
    finally:
        config_mod.get_settings.cache_clear()  # 恢复（避免影响其他测试）


def test_ensure_missing_columns_supports_indexed_columns(tmp_path):
    """桌面升级路径：索引列也能补（ADD COLUMN 后 CREATE INDEX）。"""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import declarative_base

    from app.db.migrate import ensure_missing_columns

    db_path = tmp_path / "idx.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))

    Base2 = declarative_base()

    class T(Base2):
        __tablename__ = "t"
        id = sa.Column(sa.Integer, primary_key=True)
        sector = sa.Column(sa.String(24), default="other", nullable=False, index=True)

    added = ensure_missing_columns(engine, metadata=Base2.metadata)
    assert added == ["t.sector"]
    with engine.connect() as conn:
        indexes = [str(i[1]) for i in conn.execute(text("PRAGMA index_list(t)"))]
        assert any("sector" in name for name in indexes)
    assert ensure_missing_columns(engine, metadata=Base2.metadata) == []  # 幂等
"""V0.3.1 追加测试：legacy 高校来源 sector 一次性回填。"""


def _upgrade_to2(cfg, revision: str) -> None:
    from alembic import command

    command.upgrade(cfg, revision)


def test_migration_v031_backfills_known_university_sources(tmp_path, monkeypatch):
    """已知高校来源的旧记录（sector=other）→ upgrade head → university；
    未知来源保持 other；已非 other 的值不被覆盖。"""
    import sqlite3

    from alembic.config import Config

    from app.core import config as config_mod

    db_path = tmp_path / "mig_v031.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    config_mod.get_settings.cache_clear()
    try:
        cfg = Config(str(config_mod.PROJECT_ROOT / "backend" / "alembic.ini"))
        cfg.set_main_option(
            "script_location", str(config_mod.PROJECT_ROOT / "backend" / "alembic")
        )
        _upgrade_to2(cfg, "9834a5845c71")  # V0.3（含 sector 列）
        conn = sqlite3.connect(db_path)
        for sid, sector in (
            ("sjtu_postdoc", "other"),   # 已知高校来源，V0.3 回填为 other
            ("hust_faculty", "other"),
            ("unknown_source", "other"), # 未知来源，保持 other
            ("sjtu_research", "state_owned"),  # 已有非 other 值，不覆盖
        ):
            conn.execute(
                "INSERT INTO discovered_jobs (source_id, source_name, source_url,"
                " status, sector, discovered_at, last_seen_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (sid, sid, f"https://x/{sid}", "new", sector,
                 "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
            )
        conn.commit()
        conn.close()
        _upgrade_to2(cfg, "head")
        conn = sqlite3.connect(db_path)
        rows = dict(conn.execute("SELECT source_id, sector FROM discovered_jobs"))
        conn.close()
        assert rows["sjtu_postdoc"] == "university"     # 已修正
        assert rows["hust_faculty"] == "university"
        assert rows["unknown_source"] == "other"        # 未知来源不动
        assert rows["sjtu_research"] == "state_owned"   # 非 other 不覆盖
    finally:
        config_mod.get_settings.cache_clear()


def test_backfill_legacy_sectors_function(tmp_path):
    """桌面启动路径：backfill_legacy_sectors 幂等且只动 sector='other' 的已知源。"""
    import sqlite3

    from sqlalchemy import create_engine

    from app.db.migrate import backfill_legacy_sectors

    db_path = tmp_path / "bf.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE discovered_jobs (id INTEGER PRIMARY KEY, source_id TEXT,"
            " source_url TEXT, status TEXT, sector TEXT DEFAULT 'other')"
        )
    conn = sqlite3.connect(db_path)
    for sid in ("sjtu_postdoc", "pku_rczp", "unknown_x"):
        conn.execute(
            "INSERT INTO discovered_jobs (source_id, source_url, status, sector)"
            " VALUES (?, 'https://x', 'new', 'other')", (sid,)
        )
    conn.execute(
        "INSERT INTO discovered_jobs (source_id, source_url, status, sector)"
        " VALUES ('sjtu_research', 'https://x', 'new', 'mixed')"
    )
    conn.commit()
    conn.close()

    assert backfill_legacy_sectors(engine) == 2
    conn = sqlite3.connect(db_path)
    rows = dict(conn.execute("SELECT source_id, sector FROM discovered_jobs"))
    conn.close()
    assert rows["sjtu_postdoc"] == "university"
    assert rows["pku_rczp"] == "university"
    assert rows["unknown_x"] == "other"        # 未知来源保持
    assert rows["sjtu_research"] == "mixed"    # 非 other 不覆盖

    assert backfill_legacy_sectors(engine) == 0  # 幂等
