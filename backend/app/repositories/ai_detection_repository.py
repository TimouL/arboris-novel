from typing import Optional

from sqlalchemy import select, delete

from .base import BaseRepository
from ..models import AIDetectionResult


class AIDetectionRepository(BaseRepository[AIDetectionResult]):
    model = AIDetectionResult

    async def get_latest(self, project_id: str, chapter_number: int) -> Optional[AIDetectionResult]:
        stmt = (
            select(AIDetectionResult)
            .where(
                AIDetectionResult.project_id == project_id,
                AIDetectionResult.chapter_number == chapter_number,
            )
            .order_by(AIDetectionResult.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def upsert_result(
        self,
        project_id: str,
        chapter_number: int,
        payload: dict,
    ) -> AIDetectionResult:
        existing = await self.get_latest(project_id, chapter_number)
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
            existing.project_id = project_id
            existing.chapter_number = chapter_number
            await self.session.flush()
            return existing

        instance = AIDetectionResult(
            project_id=project_id,
            chapter_number=chapter_number,
            **payload,
        )
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def clear_results(self, project_id: str, chapter_number: int) -> None:
        stmt = delete(AIDetectionResult).where(
            AIDetectionResult.project_id == project_id,
            AIDetectionResult.chapter_number == chapter_number,
        )
        await self.session.execute(stmt)
