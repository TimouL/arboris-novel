from __future__ import annotations

"""向量库后台管理服务，封装统计、查询与补录逻辑。"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.config import settings
from ..models import Chapter, ChapterOutline, NovelProject
from ..schemas.admin import (
    VectorChapterDetailResponse,
    VectorChapterListResponse,
    VectorChapterSummary,
    VectorChapterTotals,
    VectorChunkDetail,
    VectorOperationResult,
    VectorProjectListResponse,
    VectorProjectSummary,
    VectorRetrievalChunk,
    VectorRetrievalSummary,
    VectorRetrievalTestRequest,
    VectorRetrievalTestResponse,
    VectorSummaryDetail,
)
from .chapter_context_service import ChapterContextService
from .chapter_ingest_service import ChapterIngestionService
from .llm_service import LLMService
from .vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)


class VectorManagementService:
    """向量库管理操作集合，可用于管理员或项目作者。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _ensure_enabled(self) -> None:
        if not settings.vector_store_enabled:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未启用向量库，请先配置 VECTOR_DB_URL")

    def _build_vector_store(self) -> VectorStoreService:
        try:
            store = VectorStoreService()
        except RuntimeError as exc:  # pragma: no cover - 当缺少依赖时抛出
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
        if store._client is None:  # type: ignore[attr-defined]
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="向量库初始化失败")
        return store

    async def list_projects(self, *, user_id: Optional[int] = None) -> VectorProjectListResponse:
        self._ensure_enabled()
        vector_store = self._build_vector_store()

        # 从主库读取项目、章节信息
        project_query = select(NovelProject.id, NovelProject.title)
        if user_id is not None:
            project_query = project_query.where(NovelProject.user_id == user_id)
        project_rows = (await self.session.execute(project_query)).all()
        projects = {row.id: row.title for row in project_rows}

        project_ids = list(projects.keys())

        outline_query = select(ChapterOutline.project_id, ChapterOutline.chapter_number)
        if project_ids:
            outline_query = outline_query.where(ChapterOutline.project_id.in_(project_ids))
        outline_rows = (await self.session.execute(outline_query)).all()
        outline_map: Dict[str, set[int]] = defaultdict(set)
        for project_id, chapter_number in outline_rows:
            outline_map[project_id].add(chapter_number)

        chapter_query = select(
            Chapter.project_id,
            Chapter.chapter_number,
            Chapter.updated_at,
            Chapter.status,
            Chapter.selected_version_id,
        )
        if project_ids:
            chapter_query = chapter_query.where(Chapter.project_id.in_(project_ids))
        chapter_rows = await self.session.execute(chapter_query)
        chapter_meta: Dict[str, Dict[int, Tuple[Optional[datetime], str, Optional[int]]]] = defaultdict(dict)
        for project_id, chapter_number, updated_at, status_value, selected_version_id in chapter_rows.all():
            chapter_meta[project_id][chapter_number] = (
                _ensure_utc(updated_at),
                status_value,
                selected_version_id,
            )

        chunk_stats = await vector_store.fetch_chunk_stats()
        summary_stats = await vector_store.fetch_summary_stats()

        chunk_map: Dict[str, Dict[int, Dict[str, Optional[datetime] | int]]] = defaultdict(dict)
        for item in chunk_stats:
            pid = item["project_id"]
            if user_id is not None and pid not in projects:
                continue
            chunk_map[pid][item["chapter_number"]] = {
                "count": item["chunk_count"],
                "last": item["last_ingested_at"],
            }

        summary_map: Dict[str, Dict[int, Dict[str, Optional[datetime] | int]]] = defaultdict(dict)
        for item in summary_stats:
            pid = item["project_id"]
            if user_id is not None and pid not in projects:
                continue
            summary_map[pid][item["chapter_number"]] = {
                "count": item["summary_count"],
                "last": item["last_ingested_at"],
            }

        summaries: List[VectorProjectSummary] = []
        for project_id, title in projects.items():
            chapter_numbers = set(outline_map.get(project_id, set()))
            chapter_numbers.update(chapter_meta.get(project_id, {}).keys())
            chapter_numbers.update(chunk_map.get(project_id, {}).keys())
            chapter_numbers.update(summary_map.get(project_id, {}).keys())

            total = len(chapter_numbers)
            ingested = partial = missing = stale = 0
            last_ingested_at: Optional[datetime] = None

            for number in chapter_numbers:
                chunk_info = chunk_map.get(project_id, {}).get(number, {})
                summary_info = summary_map.get(project_id, {}).get(number, {})
                chunk_count = int(chunk_info.get("count", 0) or 0)
                summary_count = int(summary_info.get("count", 0) or 0)
                chapter_updated = None
                meta = chapter_meta.get(project_id, {}).get(number)
                if meta:
                    chapter_updated = meta[0]
                last = _max_datetime(chunk_info.get("last"), summary_info.get("last"))
                if last and (last_ingested_at is None or last > last_ingested_at):
                    last_ingested_at = last

                needs_refresh = bool(chapter_updated and last and chapter_updated > last)
                if chunk_count > 0 and summary_count > 0:
                    ingested += 1
                    if needs_refresh:
                        stale += 1
                elif chunk_count > 0 or summary_count > 0:
                    partial += 1
                else:
                    missing += 1

            has_vectors = ingested + partial > 0
            summaries.append(
                VectorProjectSummary(
                    project_id=project_id,
                    title=title,
                    total_chapters=total,
                    ingested_chapters=ingested,
                    partial_chapters=partial,
                    missing_chapters=missing,
                    stale_chapters=stale,
                    last_ingested_at=last_ingested_at,
                    has_vectors=has_vectors,
                )
            )

        # 若某些项目在主库不存在，但向量库有残留数据，也一起列出
        known_ids = set(projects.keys())
        handled_unknown: set[str] = set()
        for project_id in chunk_map:
            if project_id not in known_ids:
                if user_id is not None:
                    continue
                chapter_numbers = set(chunk_map[project_id].keys()) | set(summary_map.get(project_id, {}).keys())
                last_times: List[Optional[datetime]] = [info.get("last") for info in chunk_map[project_id].values()]
                last_times.extend(info.get("last") for info in summary_map.get(project_id, {}).values())
                summaries.append(
                    VectorProjectSummary(
                        project_id=project_id,
                        title="(未找到项目)",
                        total_chapters=len(chapter_numbers),
                        ingested_chapters=len(chapter_numbers),
                        partial_chapters=0,
                        missing_chapters=0,
                        stale_chapters=0,
                        last_ingested_at=_max_datetime(*last_times),
                        has_vectors=True,
                    )
                )
                handled_unknown.add(project_id)

        for project_id in summary_map:
            if project_id in known_ids or project_id in handled_unknown or project_id in chunk_map:
                continue
            if user_id is not None:
                continue
            chapter_numbers = set(summary_map[project_id].keys())
            last_times = [info.get("last") for info in summary_map[project_id].values()]
            summaries.append(
                VectorProjectSummary(
                    project_id=project_id,
                    title="(未找到项目)",
                    total_chapters=len(chapter_numbers),
                    ingested_chapters=0,
                    partial_chapters=len(chapter_numbers),
                    missing_chapters=0,
                    stale_chapters=0,
                    last_ingested_at=_max_datetime(*last_times),
                    has_vectors=True,
                )
            )
            handled_unknown.add(project_id)

        db_size = vector_store.get_storage_size()
        summaries.sort(
            key=lambda item: (_ensure_utc(item.last_ingested_at) or datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )
        return VectorProjectListResponse(projects=summaries, vector_db_size_bytes=db_size)

    async def list_project_chapters(self, project_id: str, *, user_id: Optional[int] = None) -> VectorChapterListResponse:
        self._ensure_enabled()
        project = await self.session.get(NovelProject, project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if user_id is not None and project.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")

        vector_store = self._build_vector_store()

        outline_rows = (await self.session.execute(
            select(ChapterOutline.chapter_number, ChapterOutline.title).where(ChapterOutline.project_id == project_id)
        )).all()
        titles = {row.chapter_number: row.title for row in outline_rows}

        chapter_rows = await self.session.execute(
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .options(selectinload(Chapter.selected_version))
        )
        chapter_list = chapter_rows.scalars().all()
        chapter_data: Dict[int, Chapter] = {item.chapter_number: item for item in chapter_list}

        chunk_stats = await vector_store.fetch_chunk_stats(project_id)
        summary_stats = await vector_store.fetch_summary_stats(project_id)

        chunk_map = {
            item["chapter_number"]: {
                "count": item["chunk_count"],
                "last": item["last_ingested_at"],
            }
            for item in chunk_stats
        }
        summary_map = {
            item["chapter_number"]: {
                "count": item["summary_count"],
                "last": item["last_ingested_at"],
            }
            for item in summary_stats
        }

        chapter_numbers = set(titles.keys())
        chapter_numbers.update(chapter_data.keys())
        chapter_numbers.update(chunk_map.keys())
        chapter_numbers.update(summary_map.keys())

        chapters: List[VectorChapterSummary] = []
        counters = {"ingested": 0, "partial": 0, "missing": 0, "stale": 0}

        for number in sorted(chapter_numbers):
            chapter = chapter_data.get(number)
            chunk_info = chunk_map.get(number, {})
            summary_info = summary_map.get(number, {})
            chunk_count = int(chunk_info.get("count", 0) or 0)
            summary_count = int(summary_info.get("count", 0) or 0)
            last = _max_datetime(chunk_info.get("last"), summary_info.get("last"))
            updated_at = _ensure_utc(chapter.updated_at) if chapter else None
            needs_refresh = bool(updated_at and last and updated_at > last)

            if chunk_count > 0 and summary_count > 0:
                status_value = "stale" if needs_refresh else "ingested"
                counters["ingested"] += 1
                if needs_refresh:
                    counters["stale"] += 1
            elif chunk_count > 0 or summary_count > 0:
                status_value = "partial"
                counters["partial"] += 1
            else:
                status_value = "missing"
                counters["missing"] += 1

            chapters.append(
                VectorChapterSummary(
                    chapter_number=number,
                    title=titles.get(number) or f"第{number}章",
                    status=status_value,
                    chunk_count=chunk_count,
                    summary_count=summary_count,
                    last_ingested_at=last,
                    confirmed=bool(chapter and chapter.selected_version_id),
                    needs_refresh=needs_refresh,
                    updated_at=updated_at,
                    word_count=chapter.word_count if chapter else None,
                )
            )

        totals = VectorChapterTotals(
            total=len(chapter_numbers),
            ingested=counters["ingested"],
            partial=counters["partial"],
            missing=counters["missing"],
            stale=counters["stale"],
        )
        return VectorChapterListResponse(project_id=project_id, totals=totals, chapters=chapters)

    async def get_chapter_detail(
        self,
        project_id: str,
        chapter_number: int,
        *,
        user_id: Optional[int] = None,
    ) -> VectorChapterDetailResponse:
        self._ensure_enabled()
        project = await self.session.get(NovelProject, project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if user_id is not None and project.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
        vector_store = self._build_vector_store()
        chunks = await vector_store.fetch_chunks_detail(project_id, chapter_number)
        summary = await vector_store.fetch_summary_detail(project_id, chapter_number)
        chunk_models = [VectorChunkDetail(**chunk) for chunk in chunks]
        summary_model = VectorSummaryDetail(**summary) if summary else None
        return VectorChapterDetailResponse(
            project_id=project_id,
            chapter_number=chapter_number,
            chunks=chunk_models,
            summary=summary_model,
        )

    async def reingest_chapters(self, project_id: str, chapter_numbers: Sequence[int], *, user_id: int) -> VectorOperationResult:
        self._ensure_enabled()
        if not chapter_numbers:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择需要重建的章节")

        project = await self.session.get(NovelProject, project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if project.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")

        vector_store = self._build_vector_store()
        llm_service = LLMService(self.session)
        ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)

        outlines_stmt: Select[Tuple[int, str]] = select(ChapterOutline.chapter_number, ChapterOutline.title).where(
            ChapterOutline.project_id == project_id
        )
        outline_rows = await self.session.execute(outlines_stmt)
        titles = {row.chapter_number: row.title for row in outline_rows}

        chapter_stmt = (
            select(Chapter)
            .where(Chapter.project_id == project_id, Chapter.chapter_number.in_(chapter_numbers))
            .options(selectinload(Chapter.selected_version))
        )
        result = await self.session.execute(chapter_stmt)
        chapters = {chapter.chapter_number: chapter for chapter in result.scalars()}

        processed = failed = skipped = 0
        for number in chapter_numbers:
            chapter = chapters.get(number)
            if not chapter or not chapter.selected_version:
                skipped += 1
                continue
            try:
                await ingestion_service.ingest_chapter(
                    project_id=project_id,
                    chapter_number=number,
                    title=titles.get(number) or f"第{number}章",
                    content=chapter.selected_version.content,
                    summary=chapter.real_summary,
                    user_id=user_id,
                )
            except Exception as exc:  # pragma: no cover - 捕获底层异常并反馈
                failed += 1
                logger.exception("章节 %s 重建向量失败: %s", number, exc)
            else:
                processed += 1

        message = ""
        if failed:
            message = "部分章节重建失败，详情见日志"
        elif skipped and not processed:
            message = "无可重建的章节"
        return VectorOperationResult(processed=processed, skipped=skipped, failed=failed, message=message or None)

    async def delete_chapters(
        self,
        project_id: str,
        chapter_numbers: Sequence[int],
        *,
        user_id: Optional[int] = None,
    ) -> VectorOperationResult:
        self._ensure_enabled()
        if not chapter_numbers:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择需要删除的章节")
        project = await self.session.get(NovelProject, project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if user_id is not None and project.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
        vector_store = self._build_vector_store()
        try:
            await vector_store.delete_by_chapters(project_id, list(chapter_numbers))
        except Exception as exc:  # pragma: no cover - 删除操作失败
            logger.exception("删除章节向量失败: %s", exc)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="删除向量失败") from exc
        return VectorOperationResult(processed=len(chapter_numbers), skipped=0, failed=0)

    async def test_retrieval(
        self,
        project_id: str,
        payload: VectorRetrievalTestRequest,
        *,
        user_id: int,
    ) -> VectorRetrievalTestResponse:
        self._ensure_enabled()
        project = await self.session.get(NovelProject, project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if project.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")

        vector_store = self._build_vector_store()
        llm_service = LLMService(self.session)
        context_service = ChapterContextService(llm_service=llm_service, vector_store=vector_store)

        top_k_chunks = payload.top_k_chunks or settings.vector_top_k_chunks
        top_k_summaries = payload.top_k_summaries or settings.vector_top_k_summaries

        context = await context_service.retrieve_for_generation(
            project_id=project_id,
            query_text=payload.query,
            user_id=user_id,
            top_k_chunks=top_k_chunks,
            top_k_summaries=top_k_summaries,
        )
        chunk_items = [
            VectorRetrievalChunk(
                chapter_number=item.chapter_number,
                chunk_index=index + 1,
                chapter_title=item.chapter_title,
                content=item.content,
                score=item.score,
            )
            for index, item in enumerate(context.chunks)
        ]
        summary_items = [
            VectorRetrievalSummary(
                chapter_number=item.chapter_number,
                title=item.title,
                summary=item.summary,
                score=item.score,
            )
            for item in context.summaries
        ]
        return VectorRetrievalTestResponse(query=context.query, chunks=chunk_items, summaries=summary_items)


def _max_datetime(*values: Optional[datetime]) -> Optional[datetime]:
    current: Optional[datetime] = None
    for value in values:
        normalized = _ensure_utc(value)
        if normalized and (current is None or normalized > current):
            current = normalized
    return current


def _ensure_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
