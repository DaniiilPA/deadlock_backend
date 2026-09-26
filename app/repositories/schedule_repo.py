import uuid
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Project,
    ProjectSchedule,
    StageEquipmentRequirement,
    StageTemplate,
    SpecialStatusWindow,
    AuditTrail
)


class ScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_project_by_id(self, project_id: uuid.UUID) -> Project | None:
        return await self._session.get(Project, project_id)

    async def get_templates_by_type_id(self, type_id: uuid.UUID) -> list[StageTemplate]:
        query = (
            select(StageTemplate)
            .where(StageTemplate.type_id == type_id)
            .order_by(StageTemplate.sequence_order.asc())
        )
        return list((await self._session.scalars(query)).all())

    async def get_schedule_by_id(self, schedule_id: uuid.UUID) -> ProjectSchedule | None:
        query = (
            select(ProjectSchedule)
            .where(ProjectSchedule.id == schedule_id)
            .options(selectinload(ProjectSchedule.equipment_requirements))
        )
        return await self._session.scalar(query)

    async def get_schedules_by_project_id(self, project_id: uuid.UUID) -> list[ProjectSchedule]:
        query = (
            select(ProjectSchedule)
            .where(ProjectSchedule.project_id == project_id)
            .options(selectinload(ProjectSchedule.equipment_requirements))
            .order_by(ProjectSchedule.sequence_order.asc())
        )
        return list((await self._session.scalars(query)).all())

    async def get_uncompleted_subsequent_stages(
        self, project_id: uuid.UUID, min_sequence: int
    ) -> list[ProjectSchedule]:
        query = (
            select(ProjectSchedule)
            .where(
                ProjectSchedule.project_id == project_id,
                ProjectSchedule.sequence_order >= min_sequence,
                ProjectSchedule.status != "COMPLETED"
            )
            .order_by(ProjectSchedule.sequence_order.asc())
        )
        return list((await self._session.scalars(query)).all())

    async def delete_schedules_by_project_id(self, project_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(ProjectSchedule).where(ProjectSchedule.project_id == project_id)
        )

    async def delete_equipment_by_schedule_id(self, schedule_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(StageEquipmentRequirement).where(
                StageEquipmentRequirement.schedule_id == schedule_id
            )
        )

    def add(self, entity) -> None:
        self._session.add(entity)

    async def get_active_special_window(self, project_id: uuid.UUID) -> SpecialStatusWindow | None:
        query = (
            select(SpecialStatusWindow)
            .where(
                SpecialStatusWindow.project_id == project_id,
                SpecialStatusWindow.actual_end_time.is_(None)
            )
            .order_by(SpecialStatusWindow.start_time.desc())
            .limit(1)
        )
        return await self._session.scalar(query)