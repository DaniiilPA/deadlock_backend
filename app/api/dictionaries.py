import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, require_roles
from app.db.models import User
from app.schemas import (
    EquipmentTypeResponse,
    ProjectTypeResponse,
    StageTemplateResponse,
    SystemSettingsResponse,
    SystemSettingsUpdate,
)
from app.services.dictionary_service import DictionaryService

router = APIRouter(prefix="/dictionaries", tags=["Dictionaries"])


def get_dictionary_service(session: AsyncSession = Depends(get_db)) -> DictionaryService:
    return DictionaryService(session)


@router.get(
    "/project-types",
    response_model=list[ProjectTypeResponse],
    summary="Список 9 типов ОКС из ТЗ",
)
async def get_project_types(
    service: DictionaryService = Depends(get_dictionary_service),
    current_user: User = Depends(get_current_user),
):
    return await service.list_project_types()


@router.get(
    "/equipment-types",
    response_model=list[EquipmentTypeResponse],
    summary="Справочник распознаваемой строительной техники",
)
async def get_equipment_types(
    service: DictionaryService = Depends(get_dictionary_service),
    current_user: User = Depends(get_current_user),
):
    return await service.list_equipment_types()


@router.get(
    "/stage-templates",
    response_model=list[StageTemplateResponse],
    summary="Шаблоны этапов для выбранного типа ОКС",
)
async def get_stage_templates(
    project_type_id: uuid.UUID,
    service: DictionaryService = Depends(get_dictionary_service),
    current_user: User = Depends(get_current_user),
):
    return await service.list_stage_templates(project_type_id)


@router.get(
    "/system-settings",
    response_model=SystemSettingsResponse,
    summary="Глобальные системные пороги по умолчанию",
)
async def get_global_settings(
    service: DictionaryService = Depends(get_dictionary_service),
    current_user: User = Depends(get_current_user),
):
    return await service.get_global_settings()


@router.put(
    "/system-settings",
    response_model=SystemSettingsResponse,
    summary="Редактирование глобальных порогов (Только Департамент)",
)
async def update_global_settings(
    payload: SystemSettingsUpdate,
    service: DictionaryService = Depends(get_dictionary_service),
    current_user: User = Depends(require_roles("admin")),
):
    return await service.update_global_settings(payload)