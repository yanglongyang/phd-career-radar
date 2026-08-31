"""全局配置：环境变量（.env）+ config/*.yaml 加载。

打包感知（V0.1.1）：PyInstaller 打包后（sys.frozen）——
- 资源目录（config/、前端静态文件、AI Prompts）位于 _MEIPASS（只读，随 exe 分发）；
- 数据目录（SQLite、pid 文件）位于 exe 同目录的 data/（可写，用户数据持久）。
未打包时保持仓库布局不变。"""

import sys
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

if getattr(sys, "frozen", False):
    # PyInstaller 打包：资源在 _MEIPASS，数据在 exe 旁
    _BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    _DATA_DIR = Path(sys.executable).parent / "data"
    PROJECT_ROOT = _BUNDLE_DIR
else:
    # backend/app/core/config.py -> 项目根目录
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    _DATA_DIR = PROJECT_ROOT / "data"

CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = _DATA_DIR
if getattr(sys, "frozen", False):
    # 打包环境：数据目录在 exe 旁且需要可写，确保存在
    DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env"),
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
    return Settings()


@lru_cache
def load_yaml_config(name: str) -> dict:
    """加载 config/ 下的 YAML 配置；文件缺失时返回空 dict，不阻塞启动。"""
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
