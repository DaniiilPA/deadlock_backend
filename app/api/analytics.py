import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_user,
    get_db,
    require_project_access,
    require_roles,
)
from app.db.models import User
from app.schemas import (
    AuditTrailResponse,
    DepartmentOverviewResponse,
    LiveSummaryResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(tags=["Analytics"])


def get_analytics_service(session: AsyncSession = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(session)


@router.get(
    "/projects/{project_id}/live-summary",
    response_model=LiveSummaryResponse,
    summary="Шапка дашборда проекта (Светофор, прогресс, онлайн-техника)",
)
async def get_live_summary(
    project_id: uuid.UUID,
    service: AnalyticsService = Depends(get_analytics_service),
    current_user: User = Depends(require_project_access()),
):
    return await service.get_live_summary(project_id)


@router.get(
    "/analytics/department-overview",
    response_model=DepartmentOverviewResponse,
    summary="Макро-экран Департамента (Все стройки города)",
)
async def get_department_overview(
    service: AnalyticsService = Depends(get_analytics_service),
    current_user: User = Depends(require_roles("admin")),  # Только Департамент
):
    return await service.get_department_overview()


@router.get(
    "/projects/{project_id}/audit-trail",
    response_model=list[AuditTrailResponse],
    summary="Журнал юридически значимых действий по объекту",
)
async def get_audit_trail(
    project_id: uuid.UUID,
    action_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    service: AnalyticsService = Depends(get_analytics_service),
    current_user: User = Depends(require_project_access()),
):
    return await service.get_audit_trail(
        project_id=project_id,
        action_type=action_type,
        limit=limit,
        offset=offset,
    )