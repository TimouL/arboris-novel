import asyncio
import hashlib
import json
import logging
import re
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from ..core.config import settings
from ..repositories.ai_detection_repository import AIDetectionRepository

logger = logging.getLogger(__name__)
_semaphore = asyncio.Semaphore(max(1, settings.ai_detection_max_concurrency))


class AIDetectionService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.timeout = settings.ai_detection_timeout_seconds
        self.session = session

    async def detect_text(
        self,
        text: str,
        project_id: str | None = None,
        chapter_number: int | None = None,
        timeout: float | None = None,
    ) -> Dict[str, Any]:
        if not text or not text.strip():
            raise ValueError("待检测文本为空")
        min_len = settings.ai_detection_min_length
        max_len = settings.ai_detection_max_length
        if len(text) < min_len or len(text) >= max_len:
            raise ValueError(f"文本长度需在 {min_len}~{max_len} 字之间（含 {min_len}，不含 {max_len}）")

        effective_timeout = max(1.0, min(timeout if timeout is not None else self.timeout, 60.0))

        async with _semaphore:
            result = await self._run_playwright(text.strip(), effective_timeout)

        if project_id and chapter_number and self.session:
            repo = AIDetectionRepository(self.session)
            await repo.upsert_result(
                project_id,
                chapter_number,
                {
                    **result,
                    "content_hash": self._hash_string(text.strip()),
                },
            )
        return result

    @staticmethod
    def _hash_string(value: str) -> str:
        hash_val = 0
        for ch in value:
            hash_val = (hash_val * 31 + ord(ch)) & 0xFFFFFFFF
        return format(hash_val, "x")

    async def _run_playwright(self, text_content: str, timeout_seconds: float) -> Dict[str, Any]:
        final_data: Optional[Dict[str, Any]] = None
        last_error_msg: Optional[str] = None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--headless=new", "--disable-blink-features=AutomationControlled"],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                    ignore_https_errors=True,
                )
                page = await context.new_page()
                client = await context.new_cdp_session(page)
                await client.send("Network.enable")

                def on_cdp_frame_received(event: Dict[str, Any]) -> None:
                    nonlocal final_data
                    try:
                        payload = event.get("response", {}).get("payloadData", "")
                        if not payload or "{" not in payload:
                            return
                        msg = json.loads(payload)
                        if "segment_labels" in msg or ("ori_confidence" in msg and "confidence" in msg):
                            final_data = msg
                    except Exception as exc:  # pragma: no cover - 防御性日志
                        logger.debug("CDP frame parse error: %s", exc)

                client.on("Network.webSocketFrameReceived", on_cdp_frame_received)

                try:
                    await page.goto("https://matrix.tencent.com/ai-detect/", wait_until="domcontentloaded")
                    textarea = page.locator("textarea").first
                    await textarea.wait_for(state="visible", timeout=int(timeout_seconds * 1000))
                    await textarea.fill(text_content)

                    btn = page.locator("button").filter(
                        has_text=re.compile(r"立即检测|Detect", re.IGNORECASE)
                    ).first
                    if await btn.count() > 0:
                        await btn.click()
                    else:
                        await page.keyboard.press("Control+Enter")

                    elapsed = 0.0
                    step = 0.5
                    while elapsed < timeout_seconds:
                        if final_data:
                            break
                        await asyncio.sleep(step)
                        elapsed += step

                except PlaywrightTimeoutError:
                    last_error_msg = "AI 检测页面操作超时"
                    logger.warning(last_error_msg)
                except Exception as exc:
                    last_error_msg = f"AI 检测过程异常: {exc}"
                    logger.warning(last_error_msg)
                finally:
                    await browser.close()
        except PlaywrightError as exc:
            message = str(exc)
            if "Executable doesn't exist" in message:
                raise RuntimeError("缺少 Playwright 浏览器，请运行 `python -m playwright install chromium` 后重试") from exc
            raise RuntimeError(f"Playwright 启动失败: {message}") from exc

        if not final_data:
            detail = last_error_msg or "未能获取检测结果，可能因外部检测站点不可访问或响应格式变化"
            raise RuntimeError(detail)
        return self._parse_result(final_data, text_content)

    def _parse_result(self, json_data: Dict[str, Any], text_content: str) -> Dict[str, Any]:
        confidence = json_data.get("confidence")
        available_uses = json_data.get("availableUses")
        segments = json_data.get("segment_labels", [])
        parsed_segments = []
        for seg in segments:
            parsed_segments.append(
                {
                    "label": seg.get("label", -1),
                    "text": seg.get("text", ""),
                }
            )
        return {
            "status": "success",
            "confidence": confidence,
            "available_uses": available_uses,
            "segments": parsed_segments,
            "text_hash": hashlib.sha256(text_content.encode("utf-8")).hexdigest(),
        }
