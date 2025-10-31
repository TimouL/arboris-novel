from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import List, Optional

from fastapi import HTTPException

from ..schemas.writing_models import WritingModelSettings
from ..services.llm_service import LLMService
from ..services.writing_model_service import WritingModelService
from ..utils.json_utils import remove_think_tags, unwrap_markdown_json
from .novel_service import ChapterVersionPayload

logger = logging.getLogger(__name__)


@dataclass
class AddonGenerationContext:
    user_id: int
    project_id: str
    chapter_number: int
    system_prompt: str
    prompt_input: str
    timeout: float = 600.0


class AddonWriterService:
    def __init__(self, llm_service: LLMService, model_service: WritingModelService):
        self.llm_service = llm_service
        self.model_service = model_service

    async def generate_versions(self, ctx: AddonGenerationContext) -> List[ChapterVersionPayload]:
        settings: WritingModelSettings = await self.model_service.get_settings()
        if not settings.enabled:
            return []
        active_models = [model for model in settings.models if model.enabled]
        if not active_models:
            return []

        results: List[ChapterVersionPayload] = []
        fallback_variants = max(settings.fallback_variants, 1)
        for model_cfg in active_models:
            per_model_variants = max(model_cfg.variants or fallback_variants, 1)
            override_config = {
                "model": model_cfg.model,
                "base_url": model_cfg.base_url,
                "api_key": model_cfg.api_key,
            }
            for variant_index in range(per_model_variants):
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
                    logger.warning(
                        "附加模型 %s 生成章节时返回 HTTPException: %s",
                        model_cfg.key,
                        exc.detail,
                    )
                    continue
                except Exception as exc:  # pragma: no cover - 防御性兜底
                    logger.exception(
                        "项目 %s 第 %s 章调用附加模型 %s 失败: %s",
                        ctx.project_id,
                        ctx.chapter_number,
                        model_cfg.key,
                        exc,
                    )
                    continue

                cleaned = remove_think_tags(response)
                normalized = unwrap_markdown_json(cleaned)
                content: str
                metadata: dict
                try:
                    parsed = json.loads(normalized)
                    if isinstance(parsed, dict) and "content" in parsed:
                        content = str(parsed.get("content"))
                        metadata = {k: v for k, v in parsed.items() if k != "content"}
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
        return results
