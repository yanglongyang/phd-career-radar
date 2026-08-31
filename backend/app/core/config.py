"""全局配置：环境变量（.env）+ config/*.yaml 加载。

打包感知（V0.1.1 final closure）：PyInstaller 打包后（sys.frozen）——
- RESOURCE_ROOT = _MEIPASS：frontend/dist、默认 config、AI Prompts（只读，随 exe 分发）；
- USER_ROOT = exe 所在目录：.env、config/（用户可编辑）、data/（SQLite、pid 文件）。
  首次运行时从 bundled 默认配置复制缺失的 config/*.yaml 到 exe 旁；
  Settings 永远编辑 exe 旁的用户配置 —— 更新程序不会覆盖个人权重/地区偏好。
未打包时保持仓库布局不变。
"""

import shutil
import sys
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CONFIG_NAMES = ("scoring.yaml", "regions.yaml", "profile.yaml", "sources.yaml")


def seed_user_config(default_config_dir: Path, user_config_dir: Path) -> None:
    """把 bundled 默认配置复制到用户目录（只复制缺失文件，不覆盖个人配置）。"""
    user_config_dir.mkdir(parents=True, exist_ok=True)
    for name in DEFAULT_CONFIG_NAMES:
        dst = user_config_dir / name
        if not dst.exists():
            src = default_config_dir / name
            if src.exists():
                shutil.copy2(src, dst)


if getattr(sys, "frozen", False):
    RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    USER_ROOT = Path(sys.executable).parent
    PROJECT_ROOT = RESOURCE_ROOT  # 兼容引用（静态托管等）
    _DEFAULT_CONFIG_DIR = RESOURCE_ROOT / "config"
    CONFIG_DIR = USER_ROOT / "config"
    DATA_DIR = USER_ROOT / "data"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # 首次运行：exe 旁 config/ 缺失时从 bundled 默认配置复制（只复制缺失文件）
    seed_user_config(_DEFAULT_CONFIG_DIR, CONFIG_DIR)
else:
    # backend/app/core/config.py -> 项目根目录
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    RESOURCE_ROOT = PROJECT_ROOT
    USER_ROOT = PROJECT_ROOT
    CONFIG_DIR = PROJECT_ROOT / "config"
    DATA_DIR = PROJECT_ROOT / "data"

ENV_FILE = USER_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PhD Career Radar"
    database_url: str = f"sqlite:///{(DATA_DIR / 'phd_career_radar.db').as_posix()}"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # AI Provider（OpenAI-compatible）。留空表示未配置，AI 功能显式报错，不伪造结果。
    llm_provider: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    return _apply_llm_secret(settings)


def _apply_llm_secret(settings: Settings, secret_file: Path | None = None) -> Settings:
    """V0.2.3：LLM_API_KEY 不以明文存 .env —— 优先用环境变量，否则从 DPAPI
    加密的密钥文件解密（launcher 与直接 uvicorn 启动都能用）。
    文件缺失/解密失败 → 保持未配置，AI 功能显式报错，不伪造结果。

    V0.2.4：密钥载荷含 {api_key, base_url} endpoint 绑定；绑定校验在
    provider 层执行（见 app/ai/provider.get_provider），这里只注入 api_key。"""
    if settings.llm_api_key:
        return settings
    from app.core.secrets import load_secret, secret_path

    payload = load_secret(secret_file or secret_path(DATA_DIR))
    if payload and payload.get("api_key"):
        settings.llm_api_key = payload["api_key"]
    return settings


@lru_cache
def load_yaml_config(name: str) -> dict:
    """加载 CONFIG_DIR 下的 YAML 配置；文件缺失时返回空 dict，不阻塞启动。"""
    path = CONFIG_DIR / name
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def get_scoring_config() -> dict:
    return load_yaml_config("scoring.yaml")


def get_profile_config() -> dict:
    return load_yaml_config("profile.yaml")


def get_regions_config() -> dict:
    return load_yaml_config("regions.yaml")
