from datetime import datetime
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Statistics(BaseModel):
    novel_count: int
    user_count: int
    api_request_count: int


class DailyRequestLimit(BaseModel):
    limit: int = Field(..., ge=0, description="匿名用户每日可用次数")


class UpdateLogRead(BaseModel):
    id: int
    content: str
    created_at: datetime
    created_by: Optional[str] = None
    is_pinned: bool

    class Config:
        from_attributes = True


class UpdateLogBase(BaseModel):
    content: Optional[str] = None
    is_pinned: Optional[bool] = None


class UpdateLogCreate(UpdateLogBase):
    content: str


class UpdateLogUpdate(UpdateLogBase):
    pass


class AdminNovelSummary(BaseModel):
    id: str
    title: str
    owner_id: int
    owner_username: str
    genre: str
    last_edited: str
    completed_chapters: int
    total_chapters: int


class VectorProjectSummary(BaseModel):
    project_id: str
    title: str
    total_chapters: int
    ingested_chapters: int
    partial_chapters: int
    missing_chapters: int
    stale_chapters: int
    last_ingested_at: Optional[datetime] = None
    has_vectors: bool


class VectorProjectListResponse(BaseModel):
    projects: List[VectorProjectSummary]
    vector_db_size_bytes: Optional[int] = None


class VectorChapterSummary(BaseModel):
    chapter_number: int
    title: str
    status: str
    chunk_count: int
    summary_count: int
    last_ingested_at: Optional[datetime] = None
    confirmed: bool
    needs_refresh: bool
    updated_at: Optional[datetime] = None
    word_count: Optional[int] = None


class VectorChapterTotals(BaseModel):
    total: int
    ingested: int
    partial: int
    missing: int
    stale: int


class VectorChapterListResponse(BaseModel):
    project_id: str
    totals: VectorChapterTotals
    chapters: List[VectorChapterSummary]


class VectorChunkDetail(BaseModel):
    chunk_index: int
    chapter_title: Optional[str] = None
    content: str
    embedding_dim: int
    metadata: Dict[str, Any]
    created_at: Optional[datetime] = None


class VectorSummaryDetail(BaseModel):
    title: str
    summary: str
    embedding_dim: int
    created_at: Optional[datetime] = None


class VectorChapterDetailResponse(BaseModel):
    project_id: str
    chapter_number: int
    chunks: List[VectorChunkDetail]
    summary: Optional[VectorSummaryDetail] = None


class VectorChapterBatchRequest(BaseModel):
    chapter_numbers: List[int]


class VectorRetrievalTestRequest(BaseModel):
    query: str
    top_k_chunks: Optional[int] = None
    top_k_summaries: Optional[int] = None


class VectorRetrievalChunk(BaseModel):
    chapter_number: int
    chunk_index: Optional[int] = None
    chapter_title: Optional[str] = None
    content: str
    score: float


class VectorRetrievalSummary(BaseModel):
    chapter_number: int
    title: str
    summary: str
    score: float


class VectorRetrievalTestResponse(BaseModel):
    query: str
    chunks: List[VectorRetrievalChunk]
    summaries: List[VectorRetrievalSummary]


class VectorOperationResult(BaseModel):
    processed: int
    skipped: int
    failed: int
    message: Optional[str] = None
