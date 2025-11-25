import logging
from typing import Set

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_admin
from ...db.session import get_session
from ...schemas.user import UserInDB
from ...schemas.writing_models import (
    WritingModelSettings,
    WritingModelTestRequest,
    WritingModelTestResponse,
)
from ...services.llm_service import LLMService
from ...services.writing_model_service import WritingModelService
from ...utils.json_utils import remove_think_tags, unwrap_markdown_json

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


@router.post("/test", response_model=WritingModelTestResponse)
async def test_writing_model_connection(
    payload: WritingModelTestRequest,
    session: AsyncSession = Depends(get_session),
    current_admin: UserInDB = Depends(get_current_admin),
) -> WritingModelTestResponse:
    if not payload.model or not payload.model.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="模型 ID 不能为空")

    llm_service = LLMService(session)
    override_config = {
        "model": payload.model.strip(),
        "base_url": (payload.base_url or "").strip() or None,
        "api_key": (payload.api_key or "").strip() or None,
    }

    system_prompt = payload.prompt or "You are a connectivity probe. Reply with a short confirmation message."
    user_prompt = "ping"

    try:
        raw_response = await llm_service.get_llm_response(
            system_prompt=system_prompt,
            conversation_history=[{"role": "user", "content": user_prompt}],
            temperature=payload.temperature,
            timeout=payload.timeout,
            response_format=None,
            user_id=current_admin.id,
            override_config=override_config,
        )
    except HTTPException as exc:  # 直接返回错误信息，保持 200 响应
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        logger.warning(
            "写作模型连通性测试失败：admin_id=%s model=%s detail=%s",
            current_admin.id,
            payload.model,
            detail,
        )
        return WritingModelTestResponse(success=False, message=detail)
    except Exception as exc:  # pragma: no cover
        logger.exception(
            "写作模型连通性测试发生未知异常：admin_id=%s model=%s error=%s",
            current_admin.id,
            payload.model,
            exc,
        )
        return WritingModelTestResponse(success=False, message=str(exc))

    cleaned = remove_think_tags(raw_response or "")
    normalized = unwrap_markdown_json(cleaned)
    preview = normalized.strip()
    if len(preview) > 200:
        preview = preview[:200] + "..."
    logger.info(
        "写作模型连通性测试成功：admin_id=%s model=%s",
        current_admin.id,
        payload.model,
    )
    return WritingModelTestResponse(success=True, message="连接成功", sample=preview or None)
