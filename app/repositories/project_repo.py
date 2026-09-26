import uuid
from typing import Sequence
from sqlalchemy import (
    case,
    cast,
    func,
    Numeric,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Alert,
    Project,
    ProjectAssignment,
    ProjectSchedule,
    ProjectType,
    SystemSetting,
)


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        return await self._session.get(Project, project_id)

    async def get_project_type_by_id(self, type_id: uuid.UUID) -> ProjectType | None:
        return await self._session.get(ProjectType, type_id)

    async def get_projects_registry(
        self,
        user_id: uuid.UUID,
        is_admin: bool = False,
        status: str | None = None,
        alert_level: str | None = None,
        special_status: str | None = None,
        type_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[tuple]:
        """
        Возвращает кортеж: (Project, current_stage_name, physical_progress_percent, 
                           min_start_date, max_end_date, critical_alerts_count).
        """
        # текущий этап
        current_stage_subq = (
            select(ProjectSchedule.substage_name)
            .where(
                ProjectSchedule.project_id == Project.id,
                ProjectSchedule.status.in_(["IN_PROGRESS", "PLANNED"]),
            )
            .order_by(ProjectSchedule.sequence_order.asc())
            .limit(1)
            .correlate(Project)
            .scalar_subquery()
        )

        # открытые красные алерты
        critical_alerts_subq = (
            select(func.count(Alert.id))
            .where(
                Alert.project_id == Project.id,
                Alert.severity == "RED",
                Alert.status == "OPEN",
            )
            .correlate(Project)
            .scalar_subquery()
        )

        # прогресс выполненных работ (%)
        total_duration = func.sum(
            func.extract("epoch", ProjectSchedule.base_end_date)
            - func.extract("epoch", ProjectSchedule.base_start_date)
        )
        completed_duration = func.sum(
            case(
                (
                    ProjectSchedule.status == "COMPLETED",
                    func.extract("epoch", ProjectSchedule.base_end_date)
                    - func.extract("epoch", ProjectSchedule.base_start_date),
                ),
                else_=0,
            )
        )

        progress_subq = (
            select(
                case(
                    (
                        total_duration > 0,
                        func.round(
                            cast((completed_duration * 100.0) / total_duration, Numeric),
                            1,
                        ),
                    ),
                    else_=0.0,
                )
            )
            .where(ProjectSchedule.project_id == Project.id)
            .correlate(Project)
            .scalar_subquery()
        )

        # календарное время (min/max даты)
        min_start_subq = (
            select(func.min(ProjectSchedule.base_start_date))
            .where(ProjectSchedule.project_id == Project.id)
            .correlate(Project)
            .scalar_subquery()
        )
        max_end_subq = (
            select(func.max(ProjectSchedule.base_end_date))
            .where(ProjectSchedule.project_id == Project.id)
            .correlate(Project)
            .scalar_subquery()
        )

        # Главный запрос
        query = select(
            Project,
            current_stage_subq.label("current_stage_name"),
            progress_subq.label("physical_progress_percent"),
            min_start_subq.label("min_start_date"),
            max_end_subq.label("max_end_date"),
            critical_alerts_subq.label("critical_alerts_count"),
        ).order_by(Project.created_at.desc())

        if not is_admin:
            user_projects_subq = select(ProjectAssignment.project_id).where(
                ProjectAssignment.user_id == user_id
            )
            query = query.where(Project.id.in_(user_projects_subq))

        # Фильтры
        if status:
            query = query.where(Project.status == status)
        if alert_level:
            query = query.where(Project.current_alert_level == alert_level)
        if special_status:
            query = query.where(Project.current_special_status == special_status)
        if type_id:
            query = query.where(Project.type_id == type_id)

        query = query.limit(limit).offset(offset)
        return (await self._session.execute(query)).all()

    async def get_assignment(
        self, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> ProjectAssignment | None:
        query = select(ProjectAssignment).where(
            ProjectAssignment.project_id == project_id,
            ProjectAssignment.user_id == user_id,
        )
        return await self._session.scalar(query)

    async def get_assignment_by_id(
        self, assignment_id: uuid.UUID
    ) -> ProjectAssignment | None:
        return await self._session.get(ProjectAssignment, assignment_id)

    async def get_project_assignments(
        self, project_id: uuid.UUID
    ) -> Sequence[ProjectAssignment]:
        query = (
            select(ProjectAssignment)
            .where(ProjectAssignment.project_id == project_id)
            .order_by(ProjectAssignment.assigned_at.desc())
        )
        return (await self._session.scalars(query)).all()

    async def delete_assignment(self, assignment: ProjectAssignment) -> None:
        await self._session.delete(assignment)

    async def get_project_settings(
        self, project_id: uuid.UUID
    ) -> SystemSetting | None:
        query = select(SystemSetting).where(SystemSetting.project_id == project_id)
        return await self._session.scalar(query)

    def add(self, entity) -> None:
        self._session.add(entity)