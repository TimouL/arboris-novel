import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

STATUS_PENDING = "pending"
STATUS_GENERATING = "generating"
STATUS_STOPPING = "stopping"
STATUS_COMPLETED = "completed"
STATUS_STOPPED = "stopped"
STATUS_ERROR = "error"


@dataclass
class ModelInitPayload:
    model_key: str
    display_name: str
    total_variants: int
    provider: Optional[str] = None
    is_primary: bool = False


@dataclass
class ModelProgressState:
    model_key: str
    display_name: str
    provider: Optional[str]
    total_variants: int
    completed_variants: int = 0
    status: str = STATUS_PENDING
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error_message: Optional[str] = None
    is_primary: bool = False
    stop_requested: bool = False
    last_update: float = field(default_factory=lambda: time.time())


@dataclass
class ChapterGenerationState:
    project_id: str
    chapter_number: int
    models: Dict[str, ModelProgressState]
    created_at: float = field(default_factory=lambda: time.time())
    expires_at: float = field(default_factory=lambda: time.time() + 900.0)

    def touch(self, ttl: float = 900.0) -> None:
        now = time.time()
        self.expires_at = now + ttl
        for model in self.models.values():
            model.last_update = now


class GenerationControl:
    """维护章节写作过程中各模型的运行状态."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._states: Dict[Tuple[str, int], ChapterGenerationState] = {}

    async def _cleanup_locked(self) -> None:
        now = time.time()
        expired_keys = [key for key, state in self._states.items() if state.expires_at < now]
        for key in expired_keys:
            self._states.pop(key, None)

    def _key(self, project_id: str, chapter_number: int) -> Tuple[str, int]:
        return (project_id, chapter_number)

    async def start_job(self, project_id: str, chapter_number: int, models: List[ModelInitPayload]) -> None:
        async with self._lock:
            await self._cleanup_locked()
            key = self._key(project_id, chapter_number)
            state = ChapterGenerationState(
                project_id=project_id,
                chapter_number=chapter_number,
                models={}
            )
            for payload in models:
                state.models[payload.model_key] = ModelProgressState(
                    model_key=payload.model_key,
                    display_name=payload.display_name,
                    provider=payload.provider,
                    total_variants=max(payload.total_variants, 0),
                    is_primary=payload.is_primary,
                )
            self._states[key] = state

    async def add_or_update_models(self, project_id: str, chapter_number: int, models: List[ModelInitPayload]) -> None:
        if not models:
            return
        async with self._lock:
            await self._cleanup_locked()
            key = self._key(project_id, chapter_number)
            state = self._states.setdefault(
                key,
                ChapterGenerationState(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    models={}
                )
            )
            for payload in models:
                existing = state.models.get(payload.model_key)
                if existing:
                    existing.display_name = payload.display_name
                    existing.provider = payload.provider
                    existing.total_variants = max(payload.total_variants, 0)
                    existing.is_primary = payload.is_primary
                    existing.status = STATUS_PENDING
                    existing.completed_variants = 0
                    existing.started_at = None
                    existing.finished_at = None
                    existing.error_message = None
                    existing.stop_requested = False
                    existing.last_update = time.time()
                else:
                    state.models[payload.model_key] = ModelProgressState(
                        model_key=payload.model_key,
                        display_name=payload.display_name,
                        provider=payload.provider,
                        total_variants=max(payload.total_variants, 0),
                        is_primary=payload.is_primary,
                    )
            state.touch()

    async def mark_model_started(self, project_id: str, chapter_number: int, model_key: str) -> None:
        async with self._lock:
            await self._cleanup_locked()
            state = self._states.get(self._key(project_id, chapter_number))
            if not state:
                return
            model = state.models.get(model_key)
            if not model:
                return
            now = time.time()
            model.status = STATUS_GENERATING if not model.stop_requested else STATUS_STOPPING
            if model.started_at is None:
                model.started_at = now
            model.last_update = now
            state.touch()

    async def increment_model_progress(self, project_id: str, chapter_number: int, model_key: str, completed_variants: int) -> None:
        async with self._lock:
            await self._cleanup_locked()
            state = self._states.get(self._key(project_id, chapter_number))
            if not state:
                return
            model = state.models.get(model_key)
            if not model:
                return
            model.completed_variants = min(model.total_variants, max(completed_variants, 0))
            if model.status in {STATUS_PENDING, STATUS_STOPPING}:
                model.status = STATUS_GENERATING
            model.last_update = time.time()
            state.touch()

    async def mark_model_completed(self, project_id: str, chapter_number: int, model_key: str) -> None:
        async with self._lock:
            await self._cleanup_locked()
            state = self._states.get(self._key(project_id, chapter_number))
            if not state:
                return
            model = state.models.get(model_key)
            if not model:
                return
            now = time.time()
            model.status = STATUS_COMPLETED
            model.finished_at = now
            model.stop_requested = False
            model.last_update = now
            state.touch()

    async def mark_model_stopped(self, project_id: str, chapter_number: int, model_key: str) -> None:
        async with self._lock:
            await self._cleanup_locked()
            state = self._states.get(self._key(project_id, chapter_number))
            if not state:
                return
            model = state.models.get(model_key)
            if not model:
                return
            now = time.time()
            model.status = STATUS_STOPPED
            model.finished_at = now
            model.stop_requested = False
            model.last_update = now
            state.touch()

    async def mark_model_error(self, project_id: str, chapter_number: int, model_key: str, message: str) -> None:
        async with self._lock:
            await self._cleanup_locked()
            state = self._states.get(self._key(project_id, chapter_number))
            if not state:
                return
            model = state.models.get(model_key)
            if not model:
                return
            now = time.time()
            model.status = STATUS_ERROR
            model.error_message = message
            model.finished_at = now
            model.stop_requested = False
            model.last_update = now
            state.touch()

    async def request_stop(self, project_id: str, chapter_number: int, model_key: str) -> bool:
        async with self._lock:
            await self._cleanup_locked()
            state = self._states.get(self._key(project_id, chapter_number))
            if not state:
                return False
            model = state.models.get(model_key)
            if not model:
                return False
            if model.is_primary:
                return False
            model.stop_requested = True
            if model.status == STATUS_GENERATING:
                model.status = STATUS_STOPPING
            model.last_update = time.time()
            state.touch()
            return True

    async def should_stop(self, project_id: str, chapter_number: int, model_key: str) -> bool:
        async with self._lock:
            await self._cleanup_locked()
            state = self._states.get(self._key(project_id, chapter_number))
            if not state:
                return False
            model = state.models.get(model_key)
            if not model:
                return False
            return model.stop_requested

    async def get_progress_snapshot(self, project_id: str, chapter_number: int) -> List[ModelProgressState]:
        async with self._lock:
            await self._cleanup_locked()
            state = self._states.get(self._key(project_id, chapter_number))
            if not state:
                return []
            state.touch()
            return [ModelProgressState(**vars(model)) for model in state.models.values()]

    async def finalize_job(self, project_id: str, chapter_number: int, ttl: float = 600.0) -> None:
        async with self._lock:
            await self._cleanup_locked()
            state = self._states.get(self._key(project_id, chapter_number))
            if not state:
                return
            state.touch(ttl)


# 全局单例
generation_control = GenerationControl()
