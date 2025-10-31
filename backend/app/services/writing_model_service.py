from __future__ import annotations

import json
import logging
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.system_config_repository import SystemConfigRepository
from ..models.system_config import SystemConfig
from ..schemas.writing_models import WritingModelConfig, WritingModelSettings

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
