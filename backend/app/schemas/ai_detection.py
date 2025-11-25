from typing import List, Optional

from pydantic import BaseModel, Field


class AIDetectionRequest(BaseModel):
    text: Optional[str] = Field(default=None, description="待检测文本，可为空表示使用当前章节选定版本内容")
    timeout_seconds: Optional[float] = Field(
        default=None,
        ge=1.0,
        description="检测超时时长（秒），为空则使用系统默认"
    )


class SegmentLabel(BaseModel):
    label: int = Field(description="0=人工,1=AI,2=疑似")
    text: str = Field(description="对应片段文本")


class AIDetectionResponse(BaseModel):
    status: str = Field(description="idle|running|success|error")
    confidence: Optional[float] = Field(default=None, description="整体 AI 浓度置信度，0-1")
    available_uses: Optional[int] = Field(default=None, description="剩余可用检测次数")
    segments: List[SegmentLabel] = Field(default_factory=list, description="分段检测结果")
    text_hash: Optional[str] = Field(default=None, description="文本哈希，便于前端校验结果是否过期")
    error_message: Optional[str] = Field(default=None, description="错误原因，status=error 时返回")
    content_hash: Optional[str] = Field(default=None, description="清洗后的正文哈希，用于前端比对")
