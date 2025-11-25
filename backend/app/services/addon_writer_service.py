from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from ..schemas.writing_models import WritingModelSettings
from ..services.llm_service import LLMService
from ..services.writing_model_service import WritingModelService
from ..utils.json_utils import remove_think_tags, unwrap_markdown_json
from .novel_service import ChapterVersionPayload
from .generation_control import (
    ModelInitPayload,
    generation_control,
)

logger = logging.getLogger(__name__)


@dataclass
class AddonGenerationContext:
    user_id: int
    project_id: str
    chapter_number: int
    system_prompt: str
    prompt_input: str
    timeout: float = 600.0
    model_keys: Optional[List[str]] = None
    continue_on_error: bool = False
    prompt_snapshot: Optional[dict] = None


class AddonWriterService:
    def __init__(self, llm_service: LLMService, model_service: WritingModelService):
        self.llm_service = llm_service
        self.model_service = model_service

    async def generate_versions(self, ctx: AddonGenerationContext) -> List[ChapterVersionPayload]:
        settings: WritingModelSettings = await self.model_service.get_settings()
        if not settings.enabled:
            return []
        active_models = [model for model in settings.models if model.enabled]
        if ctx.model_keys is not None:
            selected_keys = set(ctx.model_keys)
            active_models = [model for model in active_models if model.key in selected_keys]
        if not active_models:
            return []

        results: List[ChapterVersionPayload] = []
        fallback_variants = await self.model_service.resolve_fallback_variants()
        model_payloads: List[ModelInitPayload] = []
        model_tasks = []
        for model_cfg in active_models:
            configured_variants = (
                model_cfg.variants
                if isinstance(model_cfg.variants, int) and model_cfg.variants > 0
                else None
            )
            per_model_variants = max(configured_variants or fallback_variants, 1)
            model_payloads.append(
                ModelInitPayload(
                    model_key=model_cfg.key,
                    display_name=model_cfg.display_name,
                    total_variants=per_model_variants,
                    provider=model_cfg.provider,
                )
            )
            model_tasks.append((model_cfg, per_model_variants))

        await generation_control.add_or_update_models(
            ctx.project_id,
            ctx.chapter_number,
            model_payloads,
        )

        for model_cfg, per_model_variants in model_tasks:
            generated_count = 0
            failure_count = 0
            model_stopped = False
            await generation_control.mark_model_started(
                ctx.project_id,
                ctx.chapter_number,
                model_cfg.key,
            )
            override_config = {
                "model": model_cfg.model,
                "base_url": model_cfg.base_url,
                "api_key": model_cfg.api_key,
            }
            for variant_index in range(per_model_variants):
                if await generation_control.should_stop(
                    ctx.project_id,
                    ctx.chapter_number,
                    model_cfg.key,
                ):
                    model_stopped = True
                    await generation_control.mark_model_stopped(
                        ctx.project_id,
                        ctx.chapter_number,
                        model_cfg.key,
                    )
                    break
                try:
                    response = await self.llm_service.get_llm_response(
                        system_prompt=ctx.system_prompt,
                        conversation_history=[{"role": "user", "content": ctx.prompt_input}],
                        temperature=model_cfg.temperature,
                        user_id=ctx.user_id,
                        timeout=ctx.timeout,
                        response_format="json_object",
                        override_config=override_config,
                    )
                except HTTPException as exc:
                    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
                    if ctx.continue_on_error:
                        failure_count += 1
                        logger.warning(
                            "附加模型 %s 生成第 %s 章第 %s 个版本失败（HTTPException），根据继续策略跳过：%s",
                            model_cfg.key,
                            ctx.chapter_number,
                            variant_index + 1,
                            message,
                        )
                        continue
                    await generation_control.mark_model_error(
                        ctx.project_id,
                        ctx.chapter_number,
                        model_cfg.key,
                        message,
                    )
                    logger.warning(
                        "附加模型 %s 生成章节时返回 HTTPException: %s",
                        model_cfg.key,
                        message,
                    )
                    break
                except Exception as exc:  # pragma: no cover - 防御性兜底
                    if ctx.continue_on_error:
                        failure_count += 1
                        logger.exception(
                            "项目 %s 第 %s 章附加模型 %s 生成过程中发生异常，按照继续策略跳过：%s",
                            ctx.project_id,
                            ctx.chapter_number,
                            model_cfg.key,
                            exc,
                        )
                        continue
                    await generation_control.mark_model_error(
                        ctx.project_id,
                        ctx.chapter_number,
                        model_cfg.key,
                        str(exc),
                    )
                    logger.exception(
                        "项目 %s 第 %s 章调用附加模型 %s 失败: %s",
                        ctx.project_id,
                        ctx.chapter_number,
                        model_cfg.key,
                        exc,
                    )
                    break

                if await generation_control.should_stop(
                    ctx.project_id,
                    ctx.chapter_number,
                    model_cfg.key,
                ):
                    await generation_control.mark_model_stopped(
                        ctx.project_id,
                        ctx.chapter_number,
                        model_cfg.key,
                    )
                    break

                cleaned = remove_think_tags(response)
                normalized = unwrap_markdown_json(cleaned)
                content: str
                metadata: dict

                def _merge_content(value: Any) -> Optional[str]:
                    if isinstance(value, str):
                        return value
                    if isinstance(value, list):
                        parts = [text for item in value if (text := _merge_content(item))]
                        return "\n\n".join(parts) if parts else None
                    if isinstance(value, dict):
                        parts = []
                        title = value.get("title") or value.get("heading")
                        if title and isinstance(title, str):
                            parts.append(title)
                        for key in ("full_content", "content", "body", "text"):
                            if key in value:
                                text = _merge_content(value[key])
                                if text:
                                    parts.append(text)
                        if not parts and "raw" in value:
                            text = _merge_content(value["raw"])
                            if text:
                                parts.append(text)
                        return "\n\n".join(parts) if parts else None
                    return None

                try:
                    parsed = json.loads(normalized)
                    extracted = _merge_content(parsed)
                    if extracted:
                        content = extracted
                        metadata = {"raw": parsed}
                    else:
                        content = normalized if isinstance(parsed, str) else json.dumps(parsed, ensure_ascii=False)
                        metadata = {"raw": parsed}
                except json.JSONDecodeError:
                    logger.warning(
                        "项目 %s 第 %s 章附加模型 %s JSON 解析失败，使用原始文本",
                        ctx.project_id,
                        ctx.chapter_number,
                        model_cfg.key,
                    )
                    content = normalized
                    metadata = {}

                metadata.update(
                    {
                        "source": "addon",
                        "model_key": model_cfg.key,
                        "model_name": model_cfg.display_name,
                        "provider": model_cfg.provider,
                        "variant_index": variant_index,
                        "prompt_snapshot": ctx.prompt_snapshot,
                    }
                )
                label = f"{model_cfg.key}#{variant_index + 1}"
                results.append(
                    ChapterVersionPayload(
                        content=content,
                        metadata=metadata,
                        provider=model_cfg.provider or model_cfg.key,
                        label=label,
                    )
                )
                generated_count += 1
                await generation_control.increment_model_progress(
                    ctx.project_id,
                    ctx.chapter_number,
                    model_cfg.key,
                    generated_count,
                )

            if model_stopped:
                continue
            if generated_count == 0 and failure_count > 0:
                await generation_control.mark_model_error(
                    ctx.project_id,
                    ctx.chapter_number,
                    model_cfg.key,
                    "所有版本生成失败",
                )
            else:
                await generation_control.mark_model_completed(
                    ctx.project_id,
                    ctx.chapter_number,
                    model_cfg.key,
                )
        return results
