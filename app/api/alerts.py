import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, require_roles
from app.db.models import User
from app.schemas import (
    AlertEscalationResponse,
    AlertResolveRequest,
    AlertResponse,
    AlertTriggerRequest,
)
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["Alerts"])


def get_alert_service(session: AsyncSession = Depends(get_db)) -> AlertService:
    return AlertService(session)


@router.get(
    "",
    response_model=list[AlertResponse],
    summary="Журнал алертов (с фильтрацией)",
)
async def list_alerts(
    project_id: uuid.UUID | None = None,
    severity: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    service: AlertService = Depends(get_alert_service),
    current_user: User = Depends(get_current_user),
):
    return await service.list_alerts(
        current_user=current_user,
        project_id=project_id,
        severity=severity,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/active",
    response_model=AlertResponse | None,
    summary="Текущий открытый алерт по объекту",
)
async def get_active_alert(
    project_id: uuid.UUID,
    service: AlertService = Depends(get_alert_service),
    current_user: User = Depends(get_current_user),
):
    return await service.get_active_alert(project_id, current_user)


@router.post(
    "/trigger",
    response_model=AlertResponse,
    summary="Фиксация алерта (Используется воркером при нарушениях)",
)
async def trigger_alert(
    payload: AlertTriggerRequest,
    service: AlertService = Depends(get_alert_service),
    current_user: User = Depends(get_current_user),
):
    return await service.trigger_alert(payload)


@router.post(
    "/check-escalations",
    response_model=AlertEscalationResponse,
    summary="Инструмент воркера: проверка и эскалация протухших алертов",
)
async def check_escalations(
    service: AlertService = Depends(get_alert_service),
    current_user: User = Depends(require_roles("admin")),
):
    escalated_ids = await service.check_and_escalate_alerts()
    return AlertEscalationResponse(
        escalated_count=len(escalated_ids),
        escalated_alert_ids=escalated_ids,
    )


@router.post(
    "/{alert_id}/resolve",
    response_model=AlertResponse,
    summary="Реакция инженера на красный алерт (3 сценария)",
)
async def resolve_alert(
    alert_id: uuid.UUID,
    payload: AlertResolveRequest,
    service: AlertService = Depends(get_alert_service),
    current_user: User = Depends(require_roles("engineer")),
):
    return await service.resolve_alert(
        alert_id=alert_id,
        current_user=current_user,
        data=payload,
    )