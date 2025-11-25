import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.llm_config import (
    LLMConfigCreate,
    LLMConfigRead,
    LLMConfigTestRequest,
    LLMConfigTestResponse,
)
from ...schemas.user import UserInDB
from ...services.llm_config_service import LLMConfigService
from ...services.llm_service import LLMService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm-config", tags=["LLM Configuration"])


def get_llm_config_service(session: AsyncSession = Depends(get_session)) -> LLMConfigService:
    return LLMConfigService(session)


@router.get("", response_model=LLMConfigRead)
async def read_llm_config(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> LLMConfigRead:
    config = await service.get_config(current_user.id)
    if not config:
        logger.warning("用户 %s 尚未设置 LLM 配置", current_user.id)
        raise HTTPException(status_code=404, detail="尚未设置自定义配置")
    logger.info("用户 %s 获取 LLM 配置", current_user.id)
    return config


@router.put("", response_model=LLMConfigRead)
async def upsert_llm_config(
    payload: LLMConfigCreate,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> LLMConfigRead:
    logger.info("用户 %s 更新 LLM 配置", current_user.id)
    return await service.upsert_config(current_user.id, payload)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    deleted = await service.delete_config(current_user.id)
    if not deleted:
        logger.warning("用户 %s 删除 LLM 配置失败，未找到记录", current_user.id)
        raise HTTPException(status_code=404, detail="未找到配置")
    logger.info("用户 %s 删除 LLM 配置", current_user.id)


@router.post("/test", response_model=LLMConfigTestResponse)
async def test_llm_config(
    payload: LLMConfigTestRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> LLMConfigTestResponse:
    llm_service = LLMService(session)
    override_config = {
        "base_url": str(payload.llm_provider_url) if payload.llm_provider_url else None,
        "api_key": payload.llm_provider_api_key or None,
        "model": payload.llm_provider_model or None,
    }
    try:
        response = await llm_service.get_llm_response(
            system_prompt="You are a connectivity probe. Reply with a short confirmation message.",
            conversation_history=[{"role": "user", "content": "ping"}],
            user_id=current_user.id,
            timeout=30.0,
            response_format=None,
            override_config=override_config,
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return LLMConfigTestResponse(success=False, message=detail or "连接失败")
    except Exception as exc:  # pragma: no cover - 防御性兜底
        logger.exception("用户 %s 测试 LLM 配置时发生未知错误: %s", current_user.id, exc)
        return LLMConfigTestResponse(success=False, message=str(exc) or "连接失败")

    sample = response.strip()
    if len(sample) > 200:
        sample = sample[:200] + "..."
    return LLMConfigTestResponse(
        success=True,
        message="连接成功",
        sample=sample or None,
    )
