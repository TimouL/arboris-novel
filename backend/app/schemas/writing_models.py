from __future__ import annotations

import json
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class WritingModelConfig(BaseModel):
    key: str = Field(..., description="唯一标识符，建议使用简短英文名")
    display_name: str = Field(..., description="前端展示名称")
    provider: Optional[str] = Field(default=None, description="模型提供商，用于提示信息")
    model: str = Field(..., description="模型 ID")
    base_url: Optional[str] = Field(default=None, description="可选的自定义 Base URL")
    api_key: Optional[str] = Field(default=None, description="可选的专用 API Key")
    temperature: float = Field(default=0.9, ge=0.0, le=2.0)
    variants: int = Field(default=2, ge=1, le=10)
    enabled: bool = Field(default=True)

    @validator("key")
    def validate_key(cls, value: str) -> str:
        return value.strip()


class WritingModelSettings(BaseModel):
    enabled: bool = Field(default=False, description="是否启用多模型写作")
    fallback_variants: int = Field(default=3, ge=1, le=10)
    models: List[WritingModelConfig] = Field(default_factory=list)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: Optional[str]) -> "WritingModelSettings":
        if not raw:
            return cls()
        try:
            data = json.loads(raw)
            return cls.model_validate(data)
        except Exception:
            # 当历史数据格式不正确时回退默认配置
            return cls()
