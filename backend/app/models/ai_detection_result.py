from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class AIDetectionResult(Base):
    __tablename__ = "ai_detection_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="success")
    confidence: Mapped[float | None] = mapped_column(Float)
    available_uses: Mapped[int | None] = mapped_column(Integer)
    segments: Mapped[list[dict] | None] = mapped_column(JSON)
    text_hash: Mapped[str | None] = mapped_column(String(128))
    content_hash: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        {
            "mysql_charset": "utf8mb4",
        },
    )

