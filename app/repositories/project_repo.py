import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, ProjectAssignment


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        return await self._session.get(Project, project_id)

    async def get_assignment(
        self, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> ProjectAssignment | None:
        """Проверяет привязку пользователя к конкретному объекту"""
        query = select(ProjectAssignment).where(
            ProjectAssignment.project_id == project_id,
            ProjectAssignment.user_id == user_id,
        )
        return await self._session.scalar(query)

    def add(self, entity) -> None:
        self._session.add(entity)