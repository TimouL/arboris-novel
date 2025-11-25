from fastapi import APIRouter

from . import admin, auth, detection, detection_cache, llm_config, novels, updates, vector, writer, writing_models

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(novels.router)
api_router.include_router(writer.router)
api_router.include_router(writing_models.router)
api_router.include_router(admin.router)
api_router.include_router(updates.router)
api_router.include_router(llm_config.router)
api_router.include_router(vector.router)
api_router.include_router(detection.router)
api_router.include_router(detection_cache.router)
