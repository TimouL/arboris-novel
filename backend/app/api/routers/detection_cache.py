from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...repositories.ai_detection_repository import AIDetectionRepository
from ...schemas.ai_detection import AIDetectionResponse
from ...schemas.user import UserInDB


router = APIRouter(prefix="/api/detection", tags=["Detection"])


@router.get("/novels/{project_id}/chapters/{chapter_number}/latest", response_model=AIDetectionResponse)
async def get_latest_detection(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    repo = AIDetectionRepository(session)
    record = await repo.get_latest(project_id, chapter_number)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="暂无检测结果")
    return AIDetectionResponse(
        status=record.status,
        confidence=record.confidence,
        available_uses=record.available_uses,
        segments=record.segments or [],
        text_hash=record.text_hash,
        error_message=record.error_message,
        content_hash=record.content_hash,
    )
