import uuid
from typing import Sequence
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Project,
    ProjectAssignment,
    ProjectType,
    SystemSetting,
    ProjectSchedule,
    Alert,
)


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        return await self._session.get(Project, project_id)

    async def get_project_type_by_id(self, type_id: uuid.UUID) -> ProjectType | None:
        return await self._session.get(ProjectType, type_id)

    async def get_projects_for_user(
        self,
        user_id: uuid.UUID,
        is_admin: bool = False,
        status: str | None = None,
        alert_level: str | None = None,
        special_status: str | None = None,
        type_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Project]:
        """
        Админ видит все ОКС. 
        Остальные сотрудники видят только те, где они есть в project_assignments.
        """
        query = (
            select(Project)
            .options(
                selectinload(Project.schedules),
                selectinload(Project.alerts),
            )
            .order_by(Project.created_at.desc())
        )

        if not is_admin:
            query = query.join(
                ProjectAssignment, ProjectAssignment.project_id == Project.id
            ).where(ProjectAssignment.user_id == user_id)

        if status:
            query = query.where(Project.status == status)
        if alert_level:
            query = query.where(Project.current_alert_level == alert_level)
        if special_status:
            query = query.where(Project.current_special_status == special_status)
        if type_id:
            query = query.where(Project.type_id == type_id)

        query = query.limit(limit).offset(offset)
        return (await self._session.scalars(query)).all()

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