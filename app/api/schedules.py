import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_project_access
from app.core.exceptions import DomainException, EntityNotFoundException
from app.db.models import User
from app.schemas import (
    ApplyTemplateRequest,
    ApplyTemplateResponse,
    CascadeShiftRequest,
    CascadeShiftResponse,
    CurrentStageRequirementsResponse,
    MessageResponse,
    ScheduleBulkSyncRequest,
    ScheduleCompleteEarlyRequest,
    ScheduleResponse,
    StageEquipmentRequirementResponse,
)
from app.services.schedule_service import ScheduleService

router = APIRouter(prefix="/projects", tags=["Schedules"])


def get_schedule_service(session: AsyncSession = Depends(get_db)) -> ScheduleService:
    return ScheduleService(session)


@router.post(
    "/{project_id}/schedules/apply-template",
    response_model=ApplyTemplateResponse,
    summary="Автогенерация графика из шаблона ТЗ (Прораб объекта / Админ)",
)
async def apply_template(
    project_id: uuid.UUID,
    payload: ApplyTemplateRequest,
    service: ScheduleService = Depends(get_schedule_service),
    current_user: User = Depends(require_project_access("foreman")),
):
    try:
        count = await service.apply_template(project_id, payload.start_date)
        return ApplyTemplateResponse(
            created_stages_count=count,
            status="DRAFT",
            message="График успешно сформирован из нормативного справочника",
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/{project_id}/schedules",
    response_model=list[ScheduleResponse],
    summary="Получение дерева этапов (Любой назначенный на объект / Админ)",
)
async def get_schedules(
    project_id: uuid.UUID,
    service: ScheduleService = Depends(get_schedule_service),
    current_user: User = Depends(require_project_access()),
):
    try:
        return await service.get_schedules(project_id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.put(
    "/{project_id}/schedules/bulk-sync",
    response_model=MessageResponse,
    summary="Пакетное сохранение правок Ганта (Прораб объекта / Админ)",
)
async def bulk_sync_schedule(
    project_id: uuid.UUID,
    payload: ScheduleBulkSyncRequest,
    service: ScheduleService = Depends(get_schedule_service),
    current_user: User = Depends(require_project_access("foreman")),
):
    try:
        await service.bulk_sync(project_id, payload.stages)
        return MessageResponse(message="График успешно обновлен")
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/{project_id}/schedules/confirm",
    response_model=MessageResponse,
    summary="Утверждение графика DRAFT -> ACTIVE (Прораб объекта / Админ)",
)
async def confirm_schedule(
    project_id: uuid.UUID,
    service: ScheduleService = Depends(get_schedule_service),
    current_user: User = Depends(require_project_access("foreman")),
):
    try:
        await service.confirm_schedule(project_id)
        return MessageResponse(message="График утвержден и переведен в статус ACTIVE")
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post(
    "/{project_id}/schedules/{schedule_id}/start",
    response_model=ScheduleResponse,
    summary="Ручной старт этапа (Прораб объекта / Админ)",
)
async def start_stage_manually(
    project_id: uuid.UUID,
    schedule_id: uuid.UUID,
    service: ScheduleService = Depends(get_schedule_service),
    current_user: User = Depends(require_project_access("foreman")),
):
    try:
        return await service.start_stage_manually(schedule_id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post(
    "/{project_id}/schedules/{schedule_id}/complete-early",
    response_model=ScheduleResponse,
    summary="Досрочное завершение этапа (Прораб объекта / Админ)",
)
async def complete_stage_early(
    project_id: uuid.UUID,
    schedule_id: uuid.UUID,
    payload: ScheduleCompleteEarlyRequest,
    service: ScheduleService = Depends(get_schedule_service),
    current_user: User = Depends(require_project_access("engineer")),
):
    try:
        return await service.complete_stage_early(
            schedule_id=schedule_id,
            actual_end_date=payload.actual_end_date,
            foreman_comment=payload.foreman_comment,
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post(
    "/{project_id}/schedules/cascade-shift",
    response_model=CascadeShiftResponse,
    summary="Каскадный сдвиг сроков цепочки этапов (Инженер объекта / Админ)",
)
async def cascade_shift(
    project_id: uuid.UUID,
    payload: CascadeShiftRequest,
    service: ScheduleService = Depends(get_schedule_service),
    current_user: User = Depends(require_project_access("engineer")),
):
    try:
        return await service.cascade_shift(
            project_id=project_id,
            from_schedule_id=payload.from_schedule_id,
            shift_days=payload.shift_days,
            target_timeline=payload.target_timeline,
            reason_comment=payload.reason_comment,
            document_reference=payload.document_reference,
            close_special_status=payload.close_special_status,
            user_id=current_user.id,
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/{project_id}/schedules/current-requirements",
    response_model=CurrentStageRequirementsResponse | None,
    summary="Текущие требования по технике для ML-воркера",
)
async def get_current_stage_requirements(
    project_id: uuid.UUID,
    service: ScheduleService = Depends(get_schedule_service),
    current_user: User = Depends(require_project_access()),
):
    stage = await service.get_current_stage_requirements(project_id)
    if not stage:
        return None
    return CurrentStageRequirementsResponse(
        schedule_id=stage.id,
        project_id=stage.project_id,
        stage_name=stage.stage_name,
        substage_name=stage.substage_name,
        sequence_order=stage.sequence_order,
        status=stage.status,
        base_start_date=stage.base_start_date,
        base_end_date=stage.base_end_date,
        required_equipment=[
            StageEquipmentRequirementResponse.model_validate(req)
            for req in stage.equipment_requirements
        ],
    )