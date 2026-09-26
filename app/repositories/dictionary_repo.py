import uuid
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    EquipmentType,
    ProjectType,
    StageTemplate,
    SystemSetting,
)


class DictionaryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_project_types(self) -> Sequence[ProjectType]:
        query = select(ProjectType).where(ProjectType.is_active.is_(True)).order_by(ProjectType.name.asc())
        return (await self._session.scalars(query)).all()

    async def get_equipment_types(self) -> Sequence[EquipmentType]:
        query = select(EquipmentType).where(EquipmentType.is_active.is_(True)).order_by(EquipmentType.name.asc())
        return (await self._session.scalars(query)).all()

    async def get_stage_templates_by_type(self, type_id: uuid.UUID) -> Sequence[StageTemplate]:
        query = (
            select(StageTemplate)
            .where(StageTemplate.type_id == type_id)
            .order_by(StageTemplate.sequence_order.asc())
        )
        return (await self._session.scalars(query)).all()

    async def get_global_settings(self) -> SystemSetting | None:
        query = select(SystemSetting).where(SystemSetting.project_id.is_(None))
        return await self._session.scalar(query)

    def add(self, entity) -> None:
        self._session.add(entity)