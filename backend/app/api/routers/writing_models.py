import logging
from typing import Set

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_admin
from ...db.session import get_session
from ...schemas.user import UserInDB
from ...schemas.writing_models import WritingModelSettings
from ...services.writing_model_service import WritingModelService

router = APIRouter(prefix="/api/admin/writing-models", tags=["Writing Models"])
logger = logging.getLogger(__name__)


def get_writing_model_service(session: AsyncSession = Depends(get_session)) -> WritingModelService:
    return WritingModelService(session)


def _ensure_unique_keys(settings: WritingModelSettings) -> None:
    keys: Set[str] = set()
    for model in settings.models:
        if model.key in keys:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"模型 key '{model.key}' 重复")
        keys.add(model.key)


@router.get("/settings", response_model=WritingModelSettings)
async def read_writing_model_settings(
    service: WritingModelService = Depends(get_writing_model_service),
    _: UserInDB = Depends(get_current_admin),
) -> WritingModelSettings:
    settings = await service.get_settings()
    logger.info("管理员获取写作模型配置，启用状态=%s，模型数=%s", settings.enabled, len(settings.models))
    return settings


@router.put("/settings", response_model=WritingModelSettings)
async def update_writing_model_settings(
    payload: WritingModelSettings,
    service: WritingModelService = Depends(get_writing_model_service),
    _: UserInDB = Depends(get_current_admin),
) -> WritingModelSettings:
    _ensure_unique_keys(payload)
    updated = await service.save_settings(payload)
    logger.info(
        "管理员更新写作模型配置，启用状态=%s，模型数=%s",
        updated.enabled,
        len(updated.models),
    )
    return updated
