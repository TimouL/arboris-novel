from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...models import User as UserInDB
from ...schemas.admin import (
    VectorChapterBatchRequest,
    VectorChapterDetailResponse,
    VectorChapterListResponse,
    VectorOperationResult,
    VectorProjectListResponse,
    VectorRetrievalTestRequest,
    VectorRetrievalTestResponse,
)
from ...services.vector_management_service import VectorManagementService

router = APIRouter(prefix="/api/vector", tags=["Vector"])


def get_vector_service(session: AsyncSession = Depends(get_session)) -> VectorManagementService:
    return VectorManagementService(session)


@router.get("/projects", response_model=VectorProjectListResponse)
async def list_projects(
    service: VectorManagementService = Depends(get_vector_service),
    current_user: UserInDB = Depends(get_current_user),
) -> VectorProjectListResponse:
    return await service.list_projects(user_id=current_user.id)


@router.get("/projects/{project_id}/chapters", response_model=VectorChapterListResponse)
async def list_project_chapters(
    project_id: str,
    service: VectorManagementService = Depends(get_vector_service),
    current_user: UserInDB = Depends(get_current_user),
) -> VectorChapterListResponse:
    return await service.list_project_chapters(project_id, user_id=current_user.id)


@router.get(
    "/projects/{project_id}/chapters/{chapter_number}",
    response_model=VectorChapterDetailResponse,
)
async def get_chapter_detail(
    project_id: str,
    chapter_number: int,
    service: VectorManagementService = Depends(get_vector_service),
    current_user: UserInDB = Depends(get_current_user),
) -> VectorChapterDetailResponse:
    return await service.get_chapter_detail(project_id, chapter_number, user_id=current_user.id)


@router.post(
    "/projects/{project_id}/chapters/reingest",
    response_model=VectorOperationResult,
)
async def reingest_chapters(
    project_id: str,
    payload: VectorChapterBatchRequest,
    service: VectorManagementService = Depends(get_vector_service),
    current_user: UserInDB = Depends(get_current_user),
) -> VectorOperationResult:
    return await service.reingest_chapters(project_id, payload.chapter_numbers, user_id=current_user.id)


@router.post(
    "/projects/{project_id}/chapters/delete",
    response_model=VectorOperationResult,
)
async def delete_chapters(
    project_id: str,
    payload: VectorChapterBatchRequest,
    service: VectorManagementService = Depends(get_vector_service),
    current_user: UserInDB = Depends(get_current_user),
) -> VectorOperationResult:
    return await service.delete_chapters(project_id, payload.chapter_numbers, user_id=current_user.id)


@router.post(
    "/projects/{project_id}/retrieval-test",
    response_model=VectorRetrievalTestResponse,
)
async def test_retrieval(
    project_id: str,
    payload: VectorRetrievalTestRequest,
    service: VectorManagementService = Depends(get_vector_service),
    current_user: UserInDB = Depends(get_current_user),
) -> VectorRetrievalTestResponse:
    return await service.test_retrieval(project_id, payload, user_id=current_user.id)
