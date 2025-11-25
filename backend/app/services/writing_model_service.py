from __future__ import annotations

import json
import logging
import os
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.system_config_repository import SystemConfigRepository
from ..models.system_config import SystemConfig
from ..schemas.writing_models import (
    WritingModelConfig,
    WritingModelSettings,
    WritingModelOption,
    WritingModelOptionsResponse,
)
from ..core.config import settings as app_settings

logger = logging.getLogger(__name__)

_SETTINGS_KEY = "writer.multi_model.settings"
_FEATURE_FLAG_KEY = "feature.multi_writer.enabled"


class WritingModelService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.config_repo = SystemConfigRepository(session)

    async def get_settings(self) -> WritingModelSettings:
        record = await self.config_repo.get_by_key(_SETTINGS_KEY)
        raw_value = record.value if record else None
        settings = WritingModelSettings.from_json(raw_value)
        # feature flag 与 settings.enabled 双向兼容
        flag_record = await self.config_repo.get_by_key(_FEATURE_FLAG_KEY)
        if flag_record:
            try:
                flag_enabled = json.loads(flag_record.value)
                settings.enabled = bool(flag_enabled)
            except (TypeError, json.JSONDecodeError, ValueError):
                logger.warning("写作模型特性开关配置格式错误，将使用默认值")
        return settings

    async def save_settings(self, settings: WritingModelSettings) -> WritingModelSettings:
        serialized = settings.to_json()
        record = await self.config_repo.get_by_key(_SETTINGS_KEY)
        if record:
            record.value = serialized
        else:
            record = SystemConfig(key=_SETTINGS_KEY, value=serialized)
            self.session.add(record)

        flag_value = json.dumps(settings.enabled)
        flag_record = await self.config_repo.get_by_key(_FEATURE_FLAG_KEY)
        if flag_record:
            flag_record.value = flag_value
        else:
            self.session.add(SystemConfig(key=_FEATURE_FLAG_KEY, value=flag_value))

        await self.session.commit()
        return settings

    async def toggle_feature(self, enabled: bool) -> None:
        settings = await self.get_settings()
        settings.enabled = enabled
        await self.save_settings(settings)

    async def get_active_models(self) -> List[WritingModelConfig]:
        settings = await self.get_settings()
        if not settings.enabled:
            return []
        return [model for model in settings.models if model.enabled]

    async def resolve_fallback_variants(self) -> int:
        """获取主模型默认版本数，优先读取系统配置，其次读取环境变量，最后落到应用设置。"""
        record = await self.config_repo.get_by_key("writer.chapter_versions")
        if record:
            try:
                value = int(record.value) if record.value is not None else None
                if value and value > 0:
                    return value
            except (TypeError, ValueError):
                logger.warning("系统配置 writer.chapter_versions 值无效：%s", record.value)

        env_candidates = [
            os.getenv("WRITER_CHAPTER_VERSION_COUNT"),
            os.getenv("WRITER_CHAPTER_VERSIONS"),
        ]
        for raw in env_candidates:
            if not raw:
                continue
            try:
                value = int(raw)
                if value > 0:
                    return value
            except ValueError:
                logger.warning("环境变量设置的章节版本数无效：%s", raw)

        return max(app_settings.writer_chapter_versions, 1)

    async def get_public_options(self) -> WritingModelOptionsResponse:
        settings = await self.get_settings()
        fallback_variants = await self.resolve_fallback_variants()
        models = [
            WritingModelOption(
                key=model.key,
                display_name=model.display_name,
                provider=model.provider,
                temperature=model.temperature,
                variants=model.variants,
            )
            for model in settings.models
            if model.enabled
        ]
        return WritingModelOptionsResponse(
            enabled=settings.enabled,
            fallback_variants=fallback_variants,
            models=models,
        )

    async def update_model_variants(self, model_key: str, variants: int) -> WritingModelOptionsResponse:
        normalized = max(1, min(int(variants), 10))
        if model_key == "primary":
            record = await self.config_repo.get_by_key("writer.chapter_versions")
            if record:
                record.value = str(normalized)
            else:
                self.session.add(SystemConfig(key="writer.chapter_versions", value=str(normalized)))
            await self.session.commit()
        else:
            settings = await self.get_settings()
            target = None
            for model in settings.models:
                if model.key == model_key:
                    target = model
                    break
            if target is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="未找到指定写作模型，请刷新后重试。",
                )
            target.variants = normalized
            await self.save_settings(settings)
        return await self.get_public_options()
