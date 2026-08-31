# PyInstaller spec：PhD Career Radar（onedir，GUI 启动器 + 内嵌后端）
# 构建（必须从 backend 目录运行）：
#   cd backend
#   .venv/Scripts/python -m PyInstaller launcher.spec --noconfirm --distpath ../dist --workpath ../build
from pathlib import Path

ROOT = Path.cwd().parent          # backend/ 的上一级 = 项目根
BACKEND = ROOT / "backend"
DIST = ROOT / "frontend" / "dist"

datas = [
    (str(BACKEND / "app"), "app"),
    (str(ROOT / "config"), "config"),
    (str(DIST), "frontend/dist"),
]

a = Analysis(
    [str(ROOT / "launcher" / "launcher.py")],
    pathex=[str(BACKEND)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "sqlalchemy.dialects.sqlite",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "tkinter.test"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PhD Career Radar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PhD Career Radar",
)
