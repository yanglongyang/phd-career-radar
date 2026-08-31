"""设置 API（Phase 7）。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.services import settings as settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scoring_yaml: dict | None = None
    regions_yaml: dict | None = None
    profile_yaml: dict | None = None


@router.get("")
def get_settings():
    """读取当前配置（与 config/*.yaml 一致，改文件即生效）。"""
    return settings_service.read_settings()


@router.put("")
def update_settings(payload: SettingsPayload):
    """写回配置（备份 .bak）。权重合计校验为 100。"""
    data = {
        "scoring.yaml": payload.scoring_yaml,
        "regions.yaml": payload.regions_yaml,
        "profile.yaml": payload.profile_yaml,
    }
    data = {k: v for k, v in data.items() if v is not None}
    try:
        written = settings_service.update_settings(data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"written": written}
