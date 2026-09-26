import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DomainException,
    EntityNotFoundException,
    ProjectNotFoundException,
)
from app.db.models import (
    Project,
    ProjectAssignment,
    SystemSetting,
    User,
)
from app.repositories.project_repo import ProjectRepository
from app.repositories.user_repo import UserRepository
from app.schemas.projects import (
    ProjectCreate,
    ProjectListItemResponse,
    ProjectUpdate,
    ProjectAssignmentCreate,
)
from app.schemas.dictionaries import SystemSettingsUpdate


class ProjectService:
    def __init__(
        self,
        session: AsyncSession,
        project_repo: ProjectRepository | None = None,
        user_repo: UserRepository | None = None,
    ) -> None:
        self._session = session
        self._repo = project_repo or ProjectRepository(session)
        self._user_repo = user_repo or UserRepository(session)

    async def create_project(self, data: ProjectCreate, creator_id: uuid.UUID) -> Project:
        """Создание новой карточки ОКС в статусе DRAFT"""
        project_type = await self._repo.get_project_type_by_id(data.type_id)
        if not project_type:
            raise EntityNotFoundException("Выбранный тип проекта не существует")

        project = Project(
            name=data.name,
            address=data.address,
            type_id=data.type_id,
            creator_id=creator_id,
            status="DRAFT",
            schedule_status="DRAFT",
            current_alert_level="GREEN",
            current_special_status="NONE",
        )
        self._repo.add(project)
        await self._session.flush()

        # Создаем индивидуальные настройки под проект (по дефолту 48ч / 30мин / 7дней)
        settings = SystemSetting(
            project_id=project.id,
            yellow_to_red_timeout_hours=48,
            idle_threshold_minutes=30,
            frame_retention_days=7,
        )
        self._repo.add(settings)

        await self._session.commit()
        return project

    async def get_project(self, project_id: uuid.UUID) -> Project:
        project = await self._repo.get_by_id(project_id)
        if not project:
            raise ProjectNotFoundException(project_id)
        return project

    async def list_projects(
        self,
        current_user: User,
        status: str | None = None,
        alert_level: str | None = None,
        special_status: str | None = None,
        type_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProjectListItemResponse]:
        """
        Реестр ОКС с расчетом прогресса, текущего этапа и аварий.
        """
        is_admin = "admin" in current_user.roles
        projects = await self._repo.get_projects_for_user(
            user_id=current_user.id,
            is_admin=is_admin,
            status=status,
            alert_level=alert_level,
            special_status=special_status,
            type_id=type_id,
            limit=limit,
            offset=offset,
        )

        result: list[ProjectListItemResponse] = []
        now = datetime.now(timezone.utc)

        for proj in projects:
            schedules = proj.schedules
            alerts = proj.alerts

            # Расчет физического прогресса по закрытым этапам
            total_duration_sec = 0.0
            completed_duration_sec = 0.0
            current_stage_name: str | None = None

            sorted_schedules = sorted(schedules, key=lambda s: s.sequence_order)

            for s in sorted_schedules:
                duration = (s.base_end_date - s.base_start_date).total_seconds()
                total_duration_sec += duration

                if s.status == "COMPLETED":
                    completed_duration_sec += duration
                elif not current_stage_name and s.status in ("IN_PROGRESS", "PLANNED"):
                    current_stage_name = s.substage_name

            physical_progress = (
                round((completed_duration_sec / total_duration_sec) * 100, 1)
                if total_duration_sec > 0
                else 0.0
            )

            # Расчет календарного времени стройки
            time_elapsed = 0.0
            if sorted_schedules:
                first_start = sorted_schedules[0].base_start_date
                last_end = sorted_schedules[-1].base_end_date
                total_span = (last_end - first_start).total_seconds()
                if total_span > 0 and now > first_start:
                    spent = (now - first_start).total_seconds()
                    time_elapsed = round(min(max(spent / total_span, 0.0), 1.0) * 100, 1)

            # Количество открытых критических алертов
            critical_alerts_count = sum(
                1 for a in alerts if a.severity == "RED" and a.status == "OPEN"
            )

            result.append(
                ProjectListItemResponse(
                    id=proj.id,
                    name=proj.name,
                    address=proj.address,
                    type_id=proj.type_id,
                    status=proj.status,
                    schedule_status=proj.schedule_status,
                    current_alert_level=proj.current_alert_level,
                    current_special_status=proj.current_special_status,
                    current_stage_name=current_stage_name,
                    physical_progress_percent=physical_progress,
                    time_elapsed_percent=time_elapsed,
                    critical_alerts_count=critical_alerts_count,
                    created_at=proj.created_at,
                )
            )

        return result

    async def update_project(self, project_id: uuid.UUID, data: ProjectUpdate) -> Project:
        project = await self.get_project(project_id)
        if data.name is not None:
            project.name = data.name
        if data.address is not None:
            project.address = data.address

        await self._session.commit()
        return project

    async def assign_user(
        self, project_id: uuid.UUID, data: ProjectAssignmentCreate
    ) -> ProjectAssignment:
        """Привязка прораба или инженера к конкретной стройке"""
        project = await self.get_project(project_id)

        target_user = await self._user_repo.get_active_by_id(data.user_id)
        if not target_user:
            raise EntityNotFoundException("Пользователь не найден")

        # Проверка соответствия глобальной квалификации и проектной роли
        if data.role_in_project not in ("foreman", "engineer"):
            raise DomainException("Недопустимая роль. Доступны только: foreman, engineer")

        if data.role_in_project not in target_user.roles and "admin" not in target_user.roles:
            raise DomainException(
                f"У пользователя нет глобальной квалификации '{data.role_in_project}'"
            )

        existing = await self._repo.get_assignment(project.id, data.user_id)
        if existing:
            raise DomainException("Пользователь уже назначен на данный объект")

        assignment = ProjectAssignment(
            project_id=project.id,
            user_id=data.user_id,
            role_in_project=data.role_in_project,
        )
        self._repo.add(assignment)
        await self._session.commit()
        return assignment

    async def remove_assignment(
        self, project_id: uuid.UUID, assignment_id: uuid.UUID
    ) -> None:
        assignment = await self._repo.get_assignment_by_id(assignment_id)
        if not assignment or assignment.project_id != project_id:
            raise EntityNotFoundException("Назначение не найдено")

        await self._repo.delete_assignment(assignment)
        await self._session.commit()

    async def update_settings(
        self, project_id: uuid.UUID, data: SystemSettingsUpdate
    ) -> SystemSetting:
        await self.get_project(project_id)
        settings = await self._repo.get_project_settings(project_id)

        if not settings:
            settings = SystemSetting(
                project_id=project_id,
                yellow_to_red_timeout_hours=data.yellow_to_red_timeout_hours,
                idle_threshold_minutes=data.idle_threshold_minutes,
                frame_retention_days=data.frame_retention_days,
            )
            self._repo.add(settings)
        else:
            settings.yellow_to_red_timeout_hours = data.yellow_to_red_timeout_hours
            settings.idle_threshold_minutes = data.idle_threshold_minutes
            settings.frame_retention_days = data.frame_retention_days

        await self._session.commit()
        return settings