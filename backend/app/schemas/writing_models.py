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
    variants: Optional[int] = Field(default=None, ge=1, le=10)
    enabled: bool = Field(default=True)

    @validator("key")
    def validate_key(cls, value: str) -> str:
        return value.strip()


class WritingModelSettings(BaseModel):
    enabled: bool = Field(default=False, description="是否启用多模型写作")
    models: List[WritingModelConfig] = Field(default_factory=list)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: Optional[str]) -> "WritingModelSettings":
        if not raw:
            return cls()
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                data.pop("fallback_variants", None)
                models = data.get("models") or []
                if isinstance(models, list):
                    for model in models:
                        if not isinstance(model, dict):
                            continue
                        variants = model.get("variants")
                        if variants is None:
                            continue
                        try:
                            value = int(variants)
                        except (TypeError, ValueError):
                            model.pop("variants", None)
                            continue
                        if value < 1:
                            model.pop("variants", None)
                            continue
                        if value > 10:
                            model["variants"] = 10
            return cls.model_validate(data)
        except Exception:
            # 当历史数据格式不正确时回退默认配置
            return cls()


class WritingModelOption(BaseModel):
    key: str
    display_name: str
    provider: Optional[str] = None
    temperature: float
    variants: Optional[int]


class WritingModelTestRequest(BaseModel):
    model: str = Field(..., description="需要检测的模型 ID")
    base_url: Optional[str] = Field(default=None, description="可选的模型 Base URL")
    api_key: Optional[str] = Field(default=None, description="可选的模型专用 API Key")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="用于探针请求的温度")
    timeout: float = Field(default=45.0, ge=5.0, le=300.0, description="探针请求超时时间（秒）")
    prompt: Optional[str] = Field(
        default=None,
        description="可选自定义提示词，未设置时使用系统默认的连通性探针提示词",
    )


class WritingModelTestResponse(BaseModel):
    success: bool
    message: str
    sample: Optional[str] = None


class WritingModelOptionsResponse(BaseModel):
    enabled: bool
    fallback_variants: int
    models: List[WritingModelOption]


class WritingModelVariantUpdateRequest(BaseModel):
    model_key: str = Field(..., description="需要更新的模型 Key，主模型使用 'primary'")
    variants: int = Field(..., ge=1, le=10, description="期望生成的版本数量，范围 1-10")
