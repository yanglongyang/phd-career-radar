import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    applications,
    collectors,
    dashboard,
    evidence,
    jobs,
    organizations,
    reputation,
)
from app.api.routes import (
    settings as settings_routes,
)
from app.core.config import PROJECT_ROOT, get_settings
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 开发便利：启动时自动补建缺失的表（生产/CI 用 alembic 管理结构）。
    # 测试通过 PCR_SKIP_STARTUP_DDL=1 跳过，避免触碰真实数据库文件。
    if os.environ.get("PCR_SKIP_STARTUP_DDL") != "1":
        Base.metadata.create_all(engine)
        # 桌面版升级：create_all 不补已有表的缺失列，这里补普通列
        # （主键/外键/唯一/索引列变更仍必须走 alembic，见 app/db/migrate.py）
        from app.db.migrate import ensure_missing_columns

        ensure_missing_columns(engine)
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
app.include_router(collectors.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name, "version": "0.1.0"}


# ---- 静态托管（V0.1.1）：frontend/dist 存在时由 FastAPI 直接提供 React SPA ----
# 日常运行不再需要 Vite/Node 进程；开发模式（dist 不存在）行为不变。
DIST_DIR = PROJECT_ROOT / "frontend" / "dist"


def mount_static(target_app: FastAPI, dist_dir: Path) -> None:
    """把 React SPA（index.html + assets）挂到目标 app；dist 不存在时静默跳过。"""
    index = dist_dir / "index.html"
    if not (dist_dir.is_dir() and index.exists()):
        return
    target_app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")

    @target_app.get("/", include_in_schema=False)
    def index_page():
        return FileResponse(index)

    @target_app.get("/{path:path}", include_in_schema=False)
    def spa_fallback(path: str):
        """React Router 前端路由回退到 index.html；
        /api 路径**绝不**由 SPA 接住 —— 未知 API 返回 404（而不是 index.html 200）。"""
        if path == "api" or path.startswith("api/"):
            return Response(status_code=404)
        return FileResponse(index)


mount_static(app, DIST_DIR)
