import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    applications,
    dashboard,
    evidence,
    jobs,
    organizations,
    reputation,
)
from app.api.routes import (
    settings as settings_routes,
)
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 开发便利：启动时自动补建缺失的表（生产/CI 用 alembic 管理结构）。
    # 测试通过 PCR_SKIP_STARTUP_DDL=1 跳过，避免触碰真实数据库文件。
    if os.environ.get("PCR_SKIP_STARTUP_DDL") != "1":
        Base.metadata.create_all(engine)
    yield


settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(organizations.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(evidence.router, prefix="/api")
app.include_router(reputation.router, prefix="/api")
app.include_router(settings_routes.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name, "version": "0.1.0"}
