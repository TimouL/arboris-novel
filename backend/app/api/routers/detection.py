import asyncio
import hashlib
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...models.novel import Chapter
from ...schemas.ai_detection import AIDetectionRequest, AIDetectionResponse
from ...schemas.user import UserInDB
from ...services.ai_detection_service import AIDetectionService
from ...repositories.ai_detection_repository import AIDetectionRepository
from ...services.novel_service import NovelService


router = APIRouter(prefix="/api/detection", tags=["Detection"])


def _clean_content(content: str) -> str:
    text = content or ""
    text = text.strip()
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    # unescape common serialized characters
    text = text.replace("\\n", "\n").replace("\\t", "\t").replace("\\\"", '"').replace("\\\\", "\\")
    return text


async def _fetch_chapter(session: AsyncSession, project_id: str, chapter_number: int) -> Optional[Chapter]:
    stmt = (
        select(Chapter)
        .options(selectinload(Chapter.selected_version))
        .where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == chapter_number,
        )
    )
    result = await session.execute(stmt)
    return result.scalars().first()


@router.post(
    "/novels/{project_id}/chapters/{chapter_number}/ai-detect",
    response_model=AIDetectionResponse,
)
async def detect_chapter_ai_density(
    project_id: str,
    chapter_number: int,
    request: AIDetectionRequest = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> AIDetectionResponse:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    chapter = await _fetch_chapter(session, project_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")

    text = (request.text or "").strip()
    if not text:
        if not chapter.selected_version or not chapter.selected_version.content:
            raise HTTPException(status_code=400, detail="章节暂无内容可检测")
        text = chapter.selected_version.content

    cleaned_text = _clean_content(text)
    min_len = settings.ai_detection_min_length
    max_len = settings.ai_detection_max_length
    if len(cleaned_text) < min_len or len(cleaned_text) >= max_len:
        raise HTTPException(
            status_code=400,
            detail=f"文本长度需在 {min_len}~{max_len} 字之间（含 {min_len}，不含 {max_len}）",
        )

    requested_timeout = request.timeout_seconds if request.timeout_seconds is not None else settings.ai_detection_timeout_seconds
    try:
        effective_timeout = float(requested_timeout)
    except (TypeError, ValueError):
        effective_timeout = settings.ai_detection_timeout_seconds
    effective_timeout = max(1.0, min(effective_timeout, 60.0))

    service = AIDetectionService(session)
    try:
        result = await asyncio.wait_for(
            service.detect_text(
                cleaned_text,
                project_id=project_id,
                chapter_number=chapter_number,
                timeout=effective_timeout,
            ),
            timeout=effective_timeout + 5,
        )
        content_hash = service._hash_string(cleaned_text)

        # 确保持久化
        repo = AIDetectionRepository(session)
        await repo.upsert_result(
            project_id,
            chapter_number,
            {
                **result,
                "content_hash": content_hash,
            },
        )
        await session.commit()

        return AIDetectionResponse(**{**result, "content_hash": content_hash})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="检测超时，请稍后重试")
    except Exception as exc:  # pragma: no cover - 防御性兜底
        raise HTTPException(status_code=502, detail=f"检测失败：{str(exc)[:200]}") from exc
