import uuid
from datetime import datetime
from typing import Sequence
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    AuditTrail,
    CameraIntervalAnalytics,
    OrangeStatusReport,
    Project,
    ProjectSchedule,
    SpecialStatusWindow,
    User,
)


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_project_for_summary(self, project_id: uuid.UUID) -> Project | None:
        query = (
            select(Project)
            .where(Project.id == project_id)
            .options(
                selectinload(Project.schedules).selectinload(
                    ProjectSchedule.equipment_requirements
                ),
            )
        )
        return await self._session.scalar(query)

    async def get_active_special_status_window(
        self, project_id: uuid.UUID
    ) -> SpecialStatusWindow | None:
        query = (
            select(SpecialStatusWindow)
            .where(
                SpecialStatusWindow.project_id == project_id,
                SpecialStatusWindow.actual_end_time.is_(None),
            )
            .order_by(SpecialStatusWindow.start_time.desc())
            .limit(1)
        )
        return await self._session.scalar(query)

    async def get_latest_intervals_per_camera(
        self, project_id: uuid.UUID, since_datetime: datetime | None = None
    ) -> Sequence[CameraIntervalAnalytics]:
        query = select(CameraIntervalAnalytics).where(
            CameraIntervalAnalytics.project_id == project_id
        )
        if since_datetime:
            query = query.where(CameraIntervalAnalytics.interval_end >= since_datetime)

        query = query.distinct(CameraIntervalAnalytics.camera_id).order_by(
            CameraIntervalAnalytics.camera_id,
            CameraIntervalAnalytics.interval_end.desc(),
        )
        return (await self._session.scalars(query)).all()

    async def get_department_counts(self) -> dict[str, int]:
        alert_query = select(
            Project.current_alert_level, func.count(Project.id)
        ).group_by(Project.current_alert_level)
        alert_counts = dict((await self._session.execute(alert_query)).all())

        special_query = select(
            Project.current_special_status, func.count(Project.id)
        ).group_by(Project.current_special_status)
        special_counts = dict((await self._session.execute(special_query)).all())

        total_query = select(func.count(Project.id))
        total_projects = await self._session.scalar(total_query) or 0

        return {
            "total_projects": total_projects,
            "green_count": alert_counts.get("GREEN", 0),
            "yellow_count": alert_counts.get("YELLOW", 0),
            "red_count": alert_counts.get("RED", 0),
            "purple_count": special_counts.get("PURPLE", 0),
            "orange_count": special_counts.get("ORANGE", 0),
        }

    async def get_total_time_lost_hours(self) -> float:
        query = select(func.coalesce(func.sum(OrangeStatusReport.time_lost_hours), 0.0))
        return float(await self._session.scalar(query) or 0.0)

    async def get_audit_trail(
        self,
        project_id: uuid.UUID,
        action_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[tuple[AuditTrail, str | None]]:
        query = (
            select(AuditTrail, User.email)
            .outerjoin(User, User.id == AuditTrail.user_id)
            .where(AuditTrail.project_id == project_id)
            .order_by(AuditTrail.created_at.desc())
        )
        if action_type:
            query = query.where(AuditTrail.action_type == action_type)

        query = query.limit(limit).offset(offset)
        return (await self._session.execute(query)).all()