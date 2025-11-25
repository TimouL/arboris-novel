from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class LLMConfigBase(BaseModel):
    llm_provider_url: Optional[HttpUrl] = Field(default=None, description="自定义 LLM 服务地址")
    llm_provider_api_key: Optional[str] = Field(default=None, description="自定义 LLM API Key")
    llm_provider_model: Optional[str] = Field(default=None, description="自定义模型名称")


class LLMConfigCreate(LLMConfigBase):
    pass


class LLMConfigRead(LLMConfigBase):
    user_id: int

    class Config:
        from_attributes = True


class LLMConfigTestRequest(BaseModel):
    llm_provider_url: Optional[HttpUrl] = Field(default=None, description="测试用的 LLM 服务地址")
    llm_provider_api_key: Optional[str] = Field(default=None, description="测试用的 LLM API Key")
    llm_provider_model: Optional[str] = Field(default=None, description="测试用的模型名称")


class LLMConfigTestResponse(BaseModel):
    success: bool
    message: str
    sample: Optional[str] = Field(default=None, description="模型返回的示例响应")
