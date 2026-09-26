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
    OrangeStatusReportCreate,
    OrangeStatusReportResponse,
    SpecialStatusCloseRequest,
    SpecialStatusResponse,
)
from app.services.alert_service import AlertService

router = APIRouter(prefix="/special-statuses", tags=["Special Statuses"])


def get_alert_service(session: AsyncSession = Depends(get_db)) -> AlertService:
    return AlertService(session)


@router.get(
    "/projects/{project_id}/current",
    response_model=SpecialStatusResponse | None,
    summary="Текущий активный спецстатус ОКС (для виджета на фронте)",
)
async def get_current_special_status(
    project_id: uuid.UUID,
    service: AlertService = Depends(get_alert_service),
    current_user: User = Depends(require_project_access()),
):
    return await service.get_current_special_status(project_id)


@router.post(
    "/windows/{window_id}/close",
    response_model=SpecialStatusResponse,
    summary="Закрытие окна спецстатуса инженером",
)
async def close_special_status(
    window_id: uuid.UUID,
    payload: SpecialStatusCloseRequest,
    service: AlertService = Depends(get_alert_service),
    current_user: User = Depends(require_roles("engineer")),
):
    return await service.close_special_status(
        window_id=window_id,
        engineer_id=current_user.id,
        close_comment=payload.close_comment,
    )


@router.post(
    "/windows/{window_id}/orange-report",
    response_model=OrangeStatusReportResponse,
    summary="Фиксация отчета разбора инцидента инженером",
)
async def create_orange_report(
    window_id: uuid.UUID,
    payload: OrangeStatusReportCreate,
    service: AlertService = Depends(get_alert_service),
    current_user: User = Depends(require_roles("engineer")),
):
    return await service.create_orange_report(
        window_id=window_id,
        engineer_id=current_user.id,
        is_plan_caught_up=payload.is_plan_caught_up,
        time_lost_hours=payload.time_lost_hours,
        responsible_party=payload.responsible_party,
        summary_meta=payload.summary_meta,
    )


@router.get(
    "/projects/{project_id}/orange-reports",
    response_model=list[OrangeStatusReportResponse],
    summary="Реестр штрафных отчетов по объекту",
)
async def list_orange_reports(
    project_id: uuid.UUID,
    service: AlertService = Depends(get_alert_service),
    current_user: User = Depends(require_project_access()),
):
    return await service.list_orange_reports(project_id)