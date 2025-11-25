import json
import json
import logging
from datetime import datetime, timezone
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...models.novel import Chapter, ChapterOutline
from ...schemas.novel import (
    ChapterGenerationProgressResponse,
    ChapterGenerationStatus,
    ChapterPromptSection,
    ChapterPromptSnapshot,
    DeleteChapterRequest,
    EditChapterRequest,
    EvaluateChapterRequest,
    GenerateChapterRequest,
    GenerateOutlineRequest,
    ModelGenerationProgress,
    NovelProject as NovelProjectSchema,
    SelectVersionRequest,
    StopModelRequest,
    UpdateChapterOutlineRequest,
)
from ...schemas.user import UserInDB
from ...services.addon_writer_service import AddonGenerationContext, AddonWriterService
from ...services.chapter_context_service import ChapterContextService
from ...services.chapter_ingest_service import ChapterIngestionService
from ...services.llm_service import LLMService
from ...services.novel_service import ChapterVersionPayload, NovelService
from ...services.prompt_service import PromptService
from ...services.vector_store_service import VectorStoreService
from ...services.writing_model_service import WritingModelService
from ...schemas.writing_models import (
    WritingModelOptionsResponse,
    WritingModelVariantUpdateRequest,
)
from ...utils.json_utils import remove_think_tags, unwrap_markdown_json
from ...services.generation_control import generation_control, ModelInitPayload

router = APIRouter(prefix="/api/writer", tags=["Writer"])
logger = logging.getLogger(__name__)


async def _load_project_schema(service: NovelService, project_id: str, user_id: int) -> NovelProjectSchema:
    return await service.get_project_schema(project_id, user_id)


def _extract_tail_excerpt(text: Optional[str], limit: int = 500) -> str:
    """截取章节结尾文本，默认保留 500 字。"""
    if not text:
        return ""
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[-limit:]


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    cjk_matches = re.findall(r"[\u4e00-\u9fff]", text)
    cjk_count = len(cjk_matches)
    total_len = len(text)
    other_count = max(0, total_len - cjk_count)
    # 估算：中文约 0.7 token/字，其他字符约 0.25 token/字符
    estimated = cjk_count * 0.7 + other_count * 0.25
    return max(1, math.ceil(estimated))


def _extract_content_from_parsed(parsed: Any) -> str:
    if isinstance(parsed, dict):
        for key in ("full_content", "content", "chapter_content", "body", "text"):
            if key in parsed:
                val = parsed[key]
                if isinstance(val, str):
                    return val
                if val is not None:
                    return json.dumps(val, ensure_ascii=False)
        return json.dumps(parsed, ensure_ascii=False)
    if isinstance(parsed, list):
        parts: List[str] = []
        for item in parsed:
            text = _extract_content_from_parsed(item)
            if text:
                parts.append(text)
        if parts:
            return "\n\n".join(parts)
        return json.dumps(parsed, ensure_ascii=False)
    return str(parsed)


def _try_cleanup_content(raw_text: str) -> Optional[tuple[str, Dict[str, Any]]]:
    if not raw_text or "{" not in raw_text:
        return None
    candidate = unwrap_markdown_json(raw_text)
    if not candidate or "{" not in candidate:
        return None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        # 尝试从不完整的 JSON 文本中直接提取 full_content/content 字段
        for key in ("full_content", "content", "chapter_content", "body", "text"):
            match = re.search(rf'"{key}"\s*:\s*"(.*)', candidate, re.DOTALL)
            if not match:
                continue
            raw_value = match.group(1)
            # 去掉可能的尾随引号/括号
            trimmed = raw_value.rstrip('"\n\r\t }],')
            try:
                unescaped = json.loads(f'"{trimmed}"') if trimmed else ""
            except json.JSONDecodeError:
                unescaped = trimmed.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
            if unescaped:
                return unescaped, {"unwrapped_raw": candidate, "cleanup_fallback": True}
        return None
    content_text = _extract_content_from_parsed(parsed)
    return content_text, {"unwrapped_raw": parsed}


def _build_prompt_snapshot(
    *,
    system_prompt: str,
    sections: List[tuple[str, str, str]],
    prompt_input: str,
) -> ChapterPromptSnapshot:
    snapshot_sections: List[ChapterPromptSection] = []
    total_tokens = _estimate_tokens(system_prompt)
    for key, title, content in sections:
        tokens = _estimate_tokens(content)
        snapshot_sections.append(
            ChapterPromptSection(
                key=key,
                title=title,
                content=content,
                tokens=tokens,
                source=title,
            )
        )
        total_tokens += tokens
    return ChapterPromptSnapshot(
        system_prompt=system_prompt,
        sections=snapshot_sections,
        total_tokens=total_tokens,
        prompt_input=prompt_input,
    )


async def _collect_previous_context(
    *,
    project,
    chapter_number: int,
    outlines_map: Dict[int, Any],
    llm_service: LLMService,
    user_id: int,
    session: AsyncSession,
    persist_real_summary: bool,
) -> Tuple[List[Dict[str, str]], str, str]:
    completed_chapters: List[Dict[str, str]] = []
    latest_prev_number = -1
    previous_summary_text = ""
    previous_tail_excerpt = ""
    dirty = False

    for existing in project.chapters:
        if existing.chapter_number >= chapter_number:
            continue
        if existing.selected_version is None or not existing.selected_version.content:
            continue

        summary_text = existing.real_summary
        if not summary_text:
            try:
                summary = await llm_service.get_summary(
                    existing.selected_version.content,
                    temperature=0.15,
                    user_id=user_id,
                    timeout=180.0,
                )
                summary_text = remove_think_tags(summary)
                if persist_real_summary:
                    existing.real_summary = summary_text
                    dirty = True
            except Exception as exc:  # pragma: no cover - 防御性兜底
                logger.warning(
                    "项目 %s 第 %s 章生成前收集上一章摘要失败: %s",
                    project.id,
                    existing.chapter_number,
                    exc,
                )
                summary_text = existing.real_summary or ""

        completed_chapters.append(
            {
                "chapter_number": existing.chapter_number,
                "title": outlines_map.get(existing.chapter_number).title if outlines_map.get(existing.chapter_number) else f"第{existing.chapter_number}章",
                "summary": summary_text,
            }
        )
        if existing.chapter_number > latest_prev_number:
            latest_prev_number = existing.chapter_number
            previous_summary_text = summary_text or ""
            previous_tail_excerpt = _extract_tail_excerpt(existing.selected_version.content)

    if dirty:
        await session.commit()

    return completed_chapters, previous_summary_text or "暂无可用摘要", previous_tail_excerpt or "暂无上一章结尾内容"


def _sanitize_blueprint(blueprint_dict: Dict[str, Any]) -> Dict[str, Any]:
    banned_blueprint_keys = {
        "chapter_outline",
        "chapter_summaries",
        "chapter_details",
        "chapter_dialogues",
        "chapter_events",
        "conversation_history",
        "character_timelines",
    }
    for key in banned_blueprint_keys:
        if key in blueprint_dict:
            blueprint_dict.pop(key, None)
    if "relationships" in blueprint_dict and blueprint_dict["relationships"]:
        for relation in blueprint_dict["relationships"]:
            if "character_from" in relation:
                relation["from"] = relation.pop("character_from")
            if "character_to" in relation:
                relation["to"] = relation.pop("character_to")
    return blueprint_dict


async def _build_prompt_snapshot_payload(
    *,
    project,
    outline,
    chapter_number: int,
    project_id: str,
    writing_notes: Optional[str],
    llm_service: LLMService,
    context_service: ChapterContextService,
    user_id: int,
    session: AsyncSession,
    persist_real_summary: bool,
    writer_prompt: str,
) -> Tuple[ChapterPromptSnapshot, str]:
    outlines_map = {item.chapter_number: item for item in project.outlines}
    completed_chapters, previous_summary_text, previous_tail_excerpt = await _collect_previous_context(
        project=project,
        chapter_number=chapter_number,
        outlines_map=outlines_map,
        llm_service=llm_service,
        user_id=user_id,
        session=session,
        persist_real_summary=persist_real_summary,
    )

    project_schema = await NovelService(session)._serialize_project(project)  # type: ignore[attr-defined]
    blueprint_dict = _sanitize_blueprint(project_schema.blueprint.model_dump())

    outline_title = outline.title or f"第{outline.chapter_number}章"
    outline_summary = outline.summary or "暂无摘要"
    query_parts = [outline_title, outline_summary]
    if writing_notes:
        query_parts.append(writing_notes)
    rag_query = "\n".join(part for part in query_parts if part)
    rag_context = await context_service.retrieve_for_generation(
        project_id=project.id,
        query_text=rag_query or outline.title or outline.summary or "",
        user_id=user_id,
    )
    chunk_count = len(rag_context.chunks) if rag_context and rag_context.chunks else 0
    summary_count = len(rag_context.summaries) if rag_context and rag_context.summaries else 0
    logger.info(
        "项目 %s 第 %s 章检索到 %s 个剧情片段和 %s 条摘要",
        project_id,
        chapter_number,
        chunk_count,
        summary_count,
    )

    blueprint_text = json.dumps(blueprint_dict, ensure_ascii=False, indent=2)
    completed_lines = [
        f"- 第{item['chapter_number']}章 - {item['title']}:{item['summary']}"
        for item in completed_chapters
    ]
    completed_section = "\n".join(completed_lines) if completed_lines else "暂无前情摘要"
    rag_chunks_text = "\n\n".join(rag_context.chunk_texts()) if rag_context and rag_context.chunks else "未检索到章节片段"
    rag_summaries_text = "\n".join(rag_context.summary_lines()) if rag_context and rag_context.summaries else "未检索到章节摘要"
    writing_notes_text = writing_notes or "无额外写作指令"

    prompt_sections = [
        ("blueprint", "世界蓝图 (JSON)", blueprint_text),
        ("previous_summary", "上一章摘要", previous_summary_text),
        ("previous_tail", "上一章结尾", previous_tail_excerpt),
        ("rag_chunks", "检索到的剧情上下文", rag_chunks_text),
        ("rag_summaries", "检索到的章节摘要", rag_summaries_text),
        (
            "chapter_goal",
            "当前章节目标",
            f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes_text}",
        ),
    ]

    prompt_input = "\n\n".join(f"[{title}]\n{content}" for _, title, content in prompt_sections if content)
    prompt_snapshot = _build_prompt_snapshot(
        system_prompt=writer_prompt,
        sections=[(key, title, content) for key, title, content in prompt_sections],
        prompt_input=prompt_input,
    )
    return prompt_snapshot, prompt_input


@router.get("/writing-models/options", response_model=WritingModelOptionsResponse)
async def get_writing_model_options(
    session: AsyncSession = Depends(get_session),
    _: UserInDB = Depends(get_current_user),
) -> WritingModelOptionsResponse:
    service = WritingModelService(session)
    return await service.get_public_options()


@router.post("/writing-models/variants", response_model=WritingModelOptionsResponse)
async def update_writing_model_variants(
    request: WritingModelVariantUpdateRequest,
    session: AsyncSession = Depends(get_session),
    _: UserInDB = Depends(get_current_user),
) -> WritingModelOptionsResponse:
    service = WritingModelService(session)
    return await service.update_model_variants(request.model_key, request.variants)


@router.post("/novels/{project_id}/chapters/generate", response_model=NovelProjectSchema)
async def generate_chapter(
    project_id: str,
    request: GenerateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)
    writing_model_service = WritingModelService(session)
    addon_writer_service = AddonWriterService(llm_service, writing_model_service)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("用户 %s 开始为项目 %s 生成第 %s 章", current_user.id, project_id, request.chapter_number)
    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        logger.warning("项目 %s 未找到第 %s 章纲要，生成流程终止", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)
    chapter.real_summary = None
    chapter.selected_version_id = None
    chapter.status = "generating"
    await session.commit()

    writer_prompt = await prompt_service.get_prompt("writing")
    if not writer_prompt:
        logger.error("未配置名为 'writing' 的写作提示词，无法生成章节内容")
        raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置 'writing' 提示词")

    # 初始化向量检索服务，若未配置则自动降级为纯提示词生成
    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，RAG 检索被禁用: %s", exc)
            vector_store = None
    context_service = ChapterContextService(llm_service=llm_service, vector_store=vector_store)
    prompt_snapshot, prompt_input = await _build_prompt_snapshot_payload(
        project=project,
        outline=outline,
        chapter_number=request.chapter_number,
        project_id=project_id,
        writing_notes=request.writing_notes,
        llm_service=llm_service,
        context_service=context_service,
        user_id=current_user.id,
        session=session,
        persist_real_summary=True,
        writer_prompt=writer_prompt,
    )
    logger.debug("章节写作提示词：%s\n%s", writer_prompt, prompt_input)

    cleanup_enabled = (
        settings.format_cleanup_enabled
        if request.format_cleanup is None
        else bool(request.format_cleanup)
    )

    async def _generate_single_version(idx: int) -> Dict:
        try:
            response = await llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": prompt_input}],
                temperature=0.9,
                user_id=current_user.id,
                timeout=600.0,
            )
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned)
            try:
                return json.loads(normalized)
            except json.JSONDecodeError as parse_err:
                logger.warning(
                    "项目 %s 第 %s 章第 %s 个版本 JSON 解析失败，将原始内容作为纯文本处理: %s",
                    project_id,
                    request.chapter_number,
                    idx + 1,
                    parse_err,
                )
                return {"content": normalized}
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "项目 %s 生成第 %s 章第 %s 个版本时发生异常: %s",
                project_id,
                request.chapter_number,
                idx + 1,
                exc,
            )
            raise HTTPException(
                status_code=500,
                detail=f"生成章节第 {idx + 1} 个版本时失败: {str(exc)[:200]}"
            )

    def _build_payload_from_variant(
        raw_variant: Any,
        *,
        base_meta: Dict[str, Any],
        label: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> ChapterVersionPayload:
        if isinstance(raw_variant, dict):
            if "content" in raw_variant and isinstance(raw_variant["content"], str):
                content_text = raw_variant["content"]
            elif "chapter_content" in raw_variant:
                content_text = str(raw_variant["chapter_content"])
            else:
                content_text = json.dumps(raw_variant, ensure_ascii=False)
            metadata = {
                key: value
                for key, value in raw_variant.items()
                if key not in {"content", "chapter_content"}
            }
        else:
            content_text = str(raw_variant)
            metadata = {"raw": raw_variant}

        if cleanup_enabled:
            cleaned = _try_cleanup_content(content_text)
            if cleaned:
                content_text, cleanup_meta = cleaned
                metadata = {**metadata, **cleanup_meta}
        merged_meta = {**metadata, **base_meta}
        return ChapterVersionPayload(
            content=content_text,
            metadata=merged_meta,
            provider=provider or merged_meta.get("provider"),
            label=label,
        )

    continue_on_error = request.error_strategy == "continue"
    version_count = await _resolve_version_count(session)
    base_models = [
        ModelInitPayload(
            model_key="primary",
            display_name="主模型",
            total_variants=version_count,
            provider="primary",
            is_primary=True,
        )
    ]
    await generation_control.start_job(
        project_id,
        request.chapter_number,
        base_models,
    )
    logger.info(
        "项目 %s 第 %s 章计划生成 %s 个版本",
        project_id,
        request.chapter_number,
        version_count,
    )
    version_payloads: List[ChapterVersionPayload] = []
    await generation_control.mark_model_started(
        project_id,
        request.chapter_number,
        "primary",
    )
    primary_successes = 0
    primary_failures = 0
    try:
        for idx in range(version_count):
            try:
                base_variant = await _generate_single_version(idx)
            except HTTPException as exc:
                message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
                if continue_on_error:
                    primary_failures += 1
                    logger.warning(
                        "项目 %s 第 %s 章主模型第 %s 个版本生成失败（HTTPException），根据继续策略跳过：%s",
                        project_id,
                        request.chapter_number,
                        idx + 1,
                        message,
                    )
                    await generation_control.increment_model_progress(
                        project_id,
                        request.chapter_number,
                        "primary",
                        idx + 1,
                    )
                    continue
                await generation_control.mark_model_error(
                    project_id,
                    request.chapter_number,
                    "primary",
                    message,
                )
                raise
            except Exception as exc:  # pragma: no cover - 防御性兜底
                if continue_on_error:
                    primary_failures += 1
                    logger.exception(
                        "项目 %s 第 %s 章主模型第 %s 个版本生成异常，按照继续策略跳过：%s",
                        project_id,
                        request.chapter_number,
                        idx + 1,
                        exc,
                    )
                    await generation_control.increment_model_progress(
                        project_id,
                        request.chapter_number,
                        "primary",
                        idx + 1,
                    )
                    continue
                await generation_control.mark_model_error(
                    project_id,
                    request.chapter_number,
                    "primary",
                    str(exc),
                )
                logger.exception(
                    "项目 %s 第 %s 章主模型生成失败: %s",
                    project_id,
                    request.chapter_number,
                    exc,
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"生成章节第 {idx + 1} 个版本时失败: {str(exc)[:200]}",
                )
            payload = _build_payload_from_variant(
                base_variant,
                base_meta={
                    "source": "primary",
                    "model_key": "primary",
                    "model_name": "主模型",
                    "variant_index": idx,
                    "provider": "primary",
                    "prompt_snapshot": prompt_snapshot.model_dump(),
                },
            )
            version_payloads.append(payload)
            primary_successes += 1
            await generation_control.increment_model_progress(
                project_id,
                request.chapter_number,
                "primary",
                idx + 1,
            )
        await generation_control.mark_model_completed(
            project_id,
            request.chapter_number,
            "primary",
        )
        addon_context = AddonGenerationContext(
            user_id=current_user.id,
            project_id=project_id,
            chapter_number=request.chapter_number,
            system_prompt=writer_prompt,
            prompt_input=prompt_input,
            model_keys=request.model_keys,
            continue_on_error=continue_on_error,
            prompt_snapshot=prompt_snapshot.model_dump(),
        )
        addon_payloads = await addon_writer_service.generate_versions(addon_context)
        if cleanup_enabled:
            cleaned_payloads: List[ChapterVersionPayload] = []
            for payload in addon_payloads:
                cleaned = _try_cleanup_content(payload.content)
                if cleaned:
                    content_text, cleanup_meta = cleaned
                    payload = ChapterVersionPayload(
                        content=content_text,
                        metadata={**payload.metadata, **cleanup_meta},
                        provider=payload.provider,
                        label=payload.label,
                    )
                cleaned_payloads.append(payload)
            addon_payloads = cleaned_payloads
        version_payloads.extend(addon_payloads)

        await novel_service.replace_chapter_versions(chapter, version_payloads)
        if not version_payloads:
            chapter.status = ChapterGenerationStatus.FAILED.value
            await session.commit()
            logger.warning(
                "项目 %s 第 %s 章生成未产生任何有效版本，章节状态已标记为失败",
                project_id,
                request.chapter_number,
            )
        elif continue_on_error and primary_failures > 0:
            logger.warning(
                "项目 %s 第 %s 章生成完成，但有 %s 个主模型版本失败后被跳过",
                project_id,
                request.chapter_number,
                primary_failures,
            )
        logger.info(
            "项目 %s 第 %s 章生成完成，写入有效版本数量：%s",
            project_id,
            request.chapter_number,
            len(version_payloads),
        )
        return await _load_project_schema(novel_service, project_id, current_user.id)
    except Exception as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        await generation_control.mark_model_error(
            project_id,
            request.chapter_number,
            "primary",
            detail,
        )
        chapter.status = ChapterGenerationStatus.FAILED.value
        await session.commit()
        raise
    finally:
        await generation_control.finalize_job(project_id, request.chapter_number)


@router.get(
    "/novels/{project_id}/chapters/{chapter_number}/generation-progress",
    response_model=ChapterGenerationProgressResponse,
)
async def get_chapter_generation_progress(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterGenerationProgressResponse:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    progress = await generation_control.get_progress_snapshot(project_id, chapter_number)

    def _to_datetime(timestamp: Optional[float]) -> Optional[datetime]:
        if timestamp is None:
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    models = [
        ModelGenerationProgress(
            model_key=item.model_key,
            display_name=item.display_name,
            provider=item.provider,
            status=item.status,
            total_variants=item.total_variants,
            completed_variants=item.completed_variants,
            is_primary=item.is_primary,
            started_at=_to_datetime(item.started_at),
            finished_at=_to_datetime(item.finished_at),
            error_message=item.error_message,
        )
        for item in progress
    ]
    return ChapterGenerationProgressResponse(models=models)


@router.get(
    "/novels/{project_id}/chapters/{chapter_number}/prompt-preview",
    response_model=ChapterPromptSnapshot,
)
async def preview_chapter_prompt(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterPromptSnapshot:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    outline = await novel_service.get_outline(project_id, chapter_number)
    if not outline:
        raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

    writer_prompt = await prompt_service.get_prompt("writing")
    if not writer_prompt:
        raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置 'writing' 提示词")

    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，RAG 检索被禁用: %s", exc)
            vector_store = None
    context_service = ChapterContextService(llm_service=llm_service, vector_store=vector_store)

    snapshot, _ = await _build_prompt_snapshot_payload(
        project=project,
        outline=outline,
        chapter_number=chapter_number,
        project_id=project_id,
        writing_notes=None,
        llm_service=llm_service,
        context_service=context_service,
        user_id=current_user.id,
        session=session,
        persist_real_summary=False,
        writer_prompt=writer_prompt,
    )
    return snapshot


@router.get(
    "/novels/{project_id}/chapters/{chapter_number}/prompt-snapshot",
    response_model=ChapterPromptSnapshot,
)
async def get_chapter_prompt_snapshot(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterPromptSnapshot:
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == chapter_number), None)
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    if not chapter.versions:
        raise HTTPException(status_code=404, detail="尚未生成版本，暂无提示词")

    def _extract_snapshot(version: Any) -> Optional[dict]:
        if not version:
            return None
        meta = getattr(version, "metadata", None) or {}
        return meta.get("prompt_snapshot")

    candidate = _extract_snapshot(chapter.selected_version)
    if not candidate:
        for version in reversed(chapter.versions):
            candidate = _extract_snapshot(version)
            if candidate:
                break
    if not candidate:
        raise HTTPException(status_code=404, detail="未找到提示词快照")

    try:
        return ChapterPromptSnapshot(**candidate)
    except Exception:
        raise HTTPException(status_code=500, detail="提示词快照格式异常，请重新生成章节")


@router.post(
    "/novels/{project_id}/chapters/{chapter_number}/stop",
    status_code=204,
)
async def stop_model_generation(
    project_id: str,
    chapter_number: int,
    request: StopModelRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Response:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    if request.model_key == "primary":
        raise HTTPException(status_code=400, detail="主模型不可停止")
    success = await generation_control.request_stop(project_id, chapter_number, request.model_key)
    if not success:
        raise HTTPException(status_code=404, detail="未找到该模型的运行状态或模型未在运行")
    return Response(status_code=204)


async def _resolve_version_count(session: AsyncSession) -> int:
    service = WritingModelService(session)
    return await service.resolve_fallback_variants()


@router.post("/novels/{project_id}/chapters/select", response_model=NovelProjectSchema)
async def select_chapter_version(
    project_id: str,
    request: SelectVersionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法选择版本", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")

    selected = await novel_service.select_chapter_version(chapter, request.version_index)
    logger.info(
        "用户 %s 选择了项目 %s 第 %s 章的第 %s 个版本",
        current_user.id,
        project_id,
        request.chapter_number,
        request.version_index,
    )
    if selected and selected.content:
        summary = await llm_service.get_summary(
            selected.content,
            temperature=0.15,
            user_id=current_user.id,
            timeout=180.0,
        )
        chapter.real_summary = remove_think_tags(summary)
        await session.commit()

        # 选定版本后同步向量库，确保后续章节可检索到最新内容
        vector_store: Optional[VectorStoreService]
        if not settings.vector_store_enabled:
            vector_store = None
        else:
            try:
                vector_store = VectorStoreService()
            except RuntimeError as exc:
                logger.warning("向量库初始化失败，跳过章节向量同步: %s", exc)
                vector_store = None

        if vector_store:
            ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
            outline = next((item for item in project.outlines if item.chapter_number == chapter.chapter_number), None)
            chapter_title = outline.title if outline and outline.title else f"第{chapter.chapter_number}章"
            await ingestion_service.ingest_chapter(
                project_id=project_id,
                chapter_number=chapter.chapter_number,
                title=chapter_title,
                content=selected.content,
                summary=chapter.real_summary,
                user_id=current_user.id,
            )
            logger.info(
                "项目 %s 第 %s 章已同步至向量库",
                project_id,
                chapter.chapter_number,
            )

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/evaluate", response_model=NovelProjectSchema)
async def evaluate_chapter(
    project_id: str,
    request: EvaluateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法执行评估", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")
    if not chapter.versions:
        logger.warning("项目 %s 第 %s 章无可评估版本", project_id, request.chapter_number)
        raise HTTPException(status_code=400, detail="无可评估的章节版本")

    evaluator_prompt = await prompt_service.get_prompt("evaluation")
    if not evaluator_prompt:
        logger.error("缺少评估提示词，项目 %s 第 %s 章评估失败", project_id, request.chapter_number)
        raise HTTPException(status_code=500, detail="缺少评估提示词，请联系管理员配置 'evaluation' 提示词")

    project_schema = await novel_service._serialize_project(project)
    blueprint_dict = project_schema.blueprint.model_dump()

    versions_to_evaluate = [
        {"version_id": idx + 1, "content": version.content}
        for idx, version in enumerate(sorted(chapter.versions, key=lambda item: item.created_at))
    ]
    # print("blueprint_dict:",blueprint_dict)
    evaluator_payload = {
        "novel_blueprint": blueprint_dict,
        "content_to_evaluate": {
            "chapter_number": chapter.chapter_number,
            "versions": versions_to_evaluate,
        },
    }

    evaluation_raw = await llm_service.get_llm_response(
        system_prompt=evaluator_prompt,
        conversation_history=[{"role": "user", "content": json.dumps(evaluator_payload, ensure_ascii=False)}],
        temperature=0.3,
        user_id=current_user.id,
        timeout=360.0,
    )
    evaluation_clean = remove_think_tags(evaluation_raw)
    await novel_service.add_chapter_evaluation(chapter, None, evaluation_clean)
    logger.info("项目 %s 第 %s 章评估完成", project_id, request.chapter_number)

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/outline", response_model=NovelProjectSchema)
async def generate_chapter_outline(
    project_id: str,
    request: GenerateOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 请求生成项目 %s 的章节大纲，起始章节 %s，数量 %s",
        current_user.id,
        project_id,
        request.start_chapter,
        request.num_chapters,
    )
    outline_prompt = await prompt_service.get_prompt("outline")
    if not outline_prompt:
        logger.error("缺少大纲提示词，项目 %s 大纲生成失败", project_id)
        raise HTTPException(status_code=500, detail="缺少大纲提示词，请联系管理员配置 'outline' 提示词")

    project_schema = await novel_service.get_project_schema(project_id, current_user.id)
    blueprint_dict = project_schema.blueprint.model_dump()

    payload = {
        "novel_blueprint": blueprint_dict,
        "wait_to_generate": {
            "start_chapter": request.start_chapter,
            "num_chapters": request.num_chapters,
        },
    }

    response = await llm_service.get_llm_response(
        system_prompt=outline_prompt,
        conversation_history=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        temperature=0.7,
        user_id=current_user.id,
        timeout=360.0,
    )
    normalized = unwrap_markdown_json(remove_think_tags(response))
    try:
        data = json.loads(normalized)
    except json.JSONDecodeError as exc:
        logger.error(
            "项目 %s 大纲生成 JSON 解析失败: %s, 原始内容预览: %s",
            project_id,
            exc,
            normalized[:500],
        )
        raise HTTPException(
            status_code=500,
            detail=f"章节大纲生成失败，AI 返回的内容格式不正确: {str(exc)}"
        ) from exc

    new_outlines = data.get("chapters", [])
    for item in new_outlines:
        stmt = (
            select(ChapterOutline)
            .where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == item.get("chapter_number"),
            )
        )
        result = await session.execute(stmt)
        record = result.scalars().first()
        if record:
            record.title = item.get("title", record.title)
            record.summary = item.get("summary", record.summary)
        else:
            session.add(
                ChapterOutline(
                    project_id=project_id,
                    chapter_number=item.get("chapter_number"),
                    title=item.get("title", ""),
                    summary=item.get("summary"),
                )
            )
    await session.commit()
    logger.info("项目 %s 章节大纲生成完成", project_id)

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/update-outline", response_model=NovelProjectSchema)
async def update_chapter_outline(
    project_id: str,
    request: UpdateChapterOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 更新项目 %s 第 %s 章大纲",
        current_user.id,
        project_id,
        request.chapter_number,
    )

    stmt = (
        select(ChapterOutline)
        .where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == request.chapter_number,
        )
    )
    result = await session.execute(stmt)
    outline = result.scalars().first()
    if not outline:
        outline = ChapterOutline(
            project_id=project_id,
            chapter_number=request.chapter_number,
        )
        session.add(outline)

    outline.title = request.title
    outline.summary = request.summary
    await session.commit()
    logger.info("项目 %s 第 %s 章大纲已更新", project_id, request.chapter_number)

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/delete", response_model=NovelProjectSchema)
async def delete_chapters(
    project_id: str,
    request: DeleteChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    if not request.chapter_numbers:
        logger.warning("项目 %s 删除章节时未提供章节号", project_id)
        raise HTTPException(status_code=400, detail="请提供要删除的章节号列表")
    novel_service = NovelService(session)
    llm_service = LLMService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 删除项目 %s 的章节 %s",
        current_user.id,
        project_id,
        request.chapter_numbers,
    )
    await novel_service.delete_chapters(project_id, request.chapter_numbers)

    # 删除章节时同步清理向量库，避免过时内容被检索
    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过章节向量删除: %s", exc)
            vector_store = None

    if vector_store:
        ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
        await ingestion_service.delete_chapters(project_id, request.chapter_numbers)
        logger.info(
            "项目 %s 已从向量库移除章节 %s",
            project_id,
            request.chapter_numbers,
        )

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/edit", response_model=NovelProjectSchema)
async def edit_chapter(
    project_id: str,
    request: EditChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter or chapter.selected_version is None:
        logger.warning("项目 %s 第 %s 章尚未生成或未选择版本，无法编辑", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节尚未生成或未选择版本")

    chapter.selected_version.content = request.content
    chapter.word_count = len(request.content)
    logger.info("用户 %s 更新了项目 %s 第 %s 章内容", current_user.id, project_id, request.chapter_number)

    if request.content.strip():
        try:
            summary = await llm_service.get_summary(
                request.content,
                temperature=0.15,
                user_id=current_user.id,
                timeout=180.0,
            )
            chapter.real_summary = remove_think_tags(summary)
        except HTTPException as exc:
            await session.rollback()
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            logger.error(
                "项目 %s 第 %s 章重新生成摘要失败: %s",
                project_id,
                request.chapter_number,
                detail,
            )
            raise HTTPException(
                status_code=exc.status_code if isinstance(exc, HTTPException) else 500,
                detail=f"重新生成章节摘要失败：{detail}",
            ) from exc
        except Exception as exc:
            await session.rollback()
            logger.exception(
                "项目 %s 第 %s 章重新生成摘要出现异常",
                project_id,
                request.chapter_number,
            )
            raise HTTPException(
                status_code=500,
                detail=f"重新生成章节摘要失败：{exc}",
            ) from exc
    await session.commit()

    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过章节向量更新: %s", exc)
            vector_store = None

    if vector_store and chapter.selected_version and chapter.selected_version.content:
        try:
            ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
            outline = next((item for item in project.outlines if item.chapter_number == chapter.chapter_number), None)
            chapter_title = outline.title if outline and outline.title else f"第{chapter.chapter_number}章"
            await ingestion_service.ingest_chapter(
                project_id=project_id,
                chapter_number=chapter.chapter_number,
                title=chapter_title,
                content=chapter.selected_version.content,
                summary=chapter.real_summary,
                user_id=current_user.id,
            )
            logger.info("项目 %s 第 %s 章更新内容已同步至向量库", project_id, chapter.chapter_number)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            logger.error(
                "项目 %s 第 %s 章向量更新失败: %s",
                project_id,
                chapter.chapter_number,
                detail,
            )
            raise HTTPException(
                status_code=exc.status_code if isinstance(exc, HTTPException) else 500,
                detail=f"章节向量更新失败：{detail}",
            ) from exc
        except Exception as exc:
            logger.exception(
                "项目 %s 第 %s 章向量更新异常",
                project_id,
                chapter.chapter_number,
            )
            raise HTTPException(
                status_code=500,
                detail=f"章节向量更新失败：{exc}",
            ) from exc

    return await novel_service.get_project_schema(project_id, current_user.id)
