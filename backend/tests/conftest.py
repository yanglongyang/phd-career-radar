"""测试夹具：每个测试使用独立的内存数据库，不触碰真实 data/ 目录。"""

import os

os.environ["PCR_SKIP_STARTUP_DDL"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _make_sessionmaker(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db_session(db_engine):
    """直接操作数据库的会话（用于没有 API 的模型级测试，如 Application/Evidence）。"""
    session = _make_sessionmaker(db_engine)()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def client(db_engine):
    TestingSession = _make_sessionmaker(db_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


JOB_PAYLOAD = {
    "title": "青年研究员（化学生物学）",
    "organization_name": "示例大学",
    "department": "化学学院",
    "job_category": "university_research",
    "province": "江苏",
    "city": "南京",
    "position_nature": "tenure_track",
    "salary_text": "年薪 30-40 万",
    "salary_min": 30,
    "salary_max": 40,
    "salary_currency": "CNY",
    "salary_period": "year",
    "guaranteed_salary_min": 22,
    "guaranteed_salary_max": 26,
    "description_raw": "招聘具有有机化学、荧光探针研究背景的青年人才，提供启动经费 50 万。",
}


@pytest.fixture()
def sample_job(client):
    resp = client.post("/api/jobs", json=JOB_PAYLOAD)
    assert resp.status_code == 201, resp.text
    return resp.json()
