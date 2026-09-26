import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_user,
    get_db,
    require_project_access,
    require_roles,
)
from app.db.models import User
from app.schemas import (
    MessageResponse,
    ProjectAssignmentCreate,
    ProjectAssignmentResponse,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectListItemResponse,
    ProjectUpdate,
    SystemSettingsResponse,
    SystemSettingsUpdate,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


def get_project_service(session: AsyncSession = Depends(get_db)) -> ProjectService:
    return ProjectService(session)


@router.post(
    "",
    response_model=ProjectDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создание карточки ОКС (Только Департамент)",
)
async def create_project(
    payload: ProjectCreate,
    service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(require_roles("admin")),
):
    return await service.create_project(payload, creator_id=current_user.id)


@router.get(
    "",
    response_model=list[ProjectListItemResponse],
    summary="Реестр строек города (Админ видит все, сотрудники, только свои)",
)
async def list_projects(
    status: str | None = None,
    alert_level: str | None = None,
    special_status: str | None = None,
    type_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(get_current_user),
):
    return await service.list_projects(
        current_user=current_user,
        status=status,
        alert_level=alert_level,
        special_status=special_status,
        type_id=type_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Паспорт конкретного ОКС",
)
async def get_project(
    project_id: uuid.UUID,
    service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(require_project_access()),
):
    return await service.get_project(project_id)


@router.patch(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Редактирование паспорта ОКС (Только Департамент)",
)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(require_roles("admin")),
):
    return await service.update_project(project_id, payload)


@router.get(
    "/{project_id}/assignments",
    response_model=list[ProjectAssignmentResponse],
    summary="Список команды, назначенной на стройку",
)
async def get_project_team(
    project_id: uuid.UUID,
    service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(require_project_access()),
):
    return await service.get_team(project_id)


@router.post(
    "/{project_id}/assignments",
    response_model=ProjectAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Привязка прораба/инженера к ОКС (Только Департамент)",
)
async def assign_user(
    project_id: uuid.UUID,
    payload: ProjectAssignmentCreate,
    service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(require_roles("admin")),
):
    return await service.assign_user(project_id, payload)


@router.delete(
    "/{project_id}/assignments/{assignment_id}",
    response_model=MessageResponse,
    summary="Отзыв сотрудника со стройки (Только Департамент)",
)
async def remove_assignment(
    project_id: uuid.UUID,
    assignment_id: uuid.UUID,
    service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(require_roles("admin")),
):
    await service.remove_assignment(project_id, assignment_id)
    return MessageResponse(message="Назначение успешно удалено")


@router.get(
    "/{project_id}/settings",
    response_model=SystemSettingsResponse,
    summary="Получение настроек порогов ОКС",
)
async def get_project_settings(
    project_id: uuid.UUID,
    service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(require_project_access()),
):
    return await service.get_settings(project_id)

@router.put(
    "/{project_id}/settings",
    response_model=SystemSettingsResponse,
    summary="Индивидуальные настройки порогов ОКС (Инженер или Админ)",
)
async def update_project_settings(
    project_id: uuid.UUID,
    payload: SystemSettingsUpdate,
    service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(require_project_access("engineer")),
):
    return await service.update_settings(project_id, payload)