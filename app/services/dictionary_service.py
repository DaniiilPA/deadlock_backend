import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EquipmentType, ProjectType, StageTemplate, SystemSetting
from app.repositories.dictionary_repo import DictionaryRepository
from app.schemas.dictionaries import SystemSettingsUpdate


class DictionaryService:
    def __init__(
        self,
        session: AsyncSession,
        repo: DictionaryRepository | None = None,
    ) -> None:
        self._session = session
        self._repo = repo or DictionaryRepository(session)

    async def list_project_types(self) -> list[ProjectType]:
        return list(await self._repo.get_project_types())

    async def list_equipment_types(self) -> list[EquipmentType]:
        return list(await self._repo.get_equipment_types())

    async def list_stage_templates(self, type_id: uuid.UUID) -> list[StageTemplate]:
        return list(await self._repo.get_stage_templates_by_type(type_id))

    async def get_global_settings(self) -> SystemSetting:
        settings = await self._repo.get_global_settings()
        if not settings:
            settings = SystemSetting(
                project_id=None,
                yellow_to_red_timeout_hours=48,
                idle_threshold_minutes=30,
                frame_retention_days=7,
            )
            self._repo.add(settings)
            await self._session.commit()
        return settings

    async def update_global_settings(self, data: SystemSettingsUpdate) -> SystemSetting:
        settings = await self.get_global_settings()
        settings.yellow_to_red_timeout_hours = data.yellow_to_red_timeout_hours
        settings.idle_threshold_minutes = data.idle_threshold_minutes
        settings.frame_retention_days = data.frame_retention_days
        await self._session.commit()
        return settings