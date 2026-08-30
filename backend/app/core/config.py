"""全局配置：环境变量（.env）+ config/*.yaml 加载。"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"


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
