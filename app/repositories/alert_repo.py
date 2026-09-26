import uuid
from datetime import datetime
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.db.models import (
    Alert,
    AlertResolution,
    OrangeStatusReport,
    Project,
    SpecialStatusWindow,
    SystemSetting,
)


class AlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_alert_by_id(self, alert_id: uuid.UUID) -> Alert | None:
        query = (
            select(Alert)
            .where(Alert.id == alert_id)
            .options(
                selectinload(Alert.resolution),
                selectinload(Alert.special_status_windows),
                selectinload(Alert.trigger_frame),
                joinedload(Alert.project),
            )
        )
        return await self._session.scalar(query)

    async def get_open_alert_by_trigger(
        self, project_id: uuid.UUID, schedule_id: uuid.UUID | None, trigger_type: str
    ) -> Alert | None:
        """Поиск открытого алерта для дедупликации с правильной обработкой NULL"""
        query = select(Alert).where(
            Alert.project_id == project_id,
            Alert.trigger_type == trigger_type,
            Alert.status == "OPEN",
        )
        if schedule_id is None:
            query = query.where(Alert.schedule_id.is_(None))
        else:
            query = query.where(Alert.schedule_id == schedule_id)

        return await self._session.scalar(query)

    async def list_alerts(
        self,
        project_id: uuid.UUID | None = None,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Alert]:
        query = select(Alert).order_by(Alert.triggered_at.desc())
        if project_id:
            query = query.where(Alert.project_id == project_id)
        if severity:
            query = query.where(Alert.severity == severity)
        if status:
            query = query.where(Alert.status == status)

        query = query.limit(limit).offset(offset)
        return (await self._session.scalars(query)).all()

    async def get_active_alert_by_project(self, project_id: uuid.UUID) -> Alert | None:
        query = (
            select(Alert)
            .where(Alert.project_id == project_id, Alert.status == "OPEN")
            .order_by(Alert.triggered_at.desc())
            .limit(1)
        )
        return await self._session.scalar(query)

    async def get_alerts_ready_to_escalate(self, now: datetime) -> Sequence[Alert]:
        """
        Сразу подгружаем связанный проект через joinedload, чтобы не делать SELECT в цикле!
        """
        query = (
            select(Alert)
            .options(joinedload(Alert.project))
            .where(
                Alert.severity == "YELLOW",
                Alert.status == "OPEN",
                Alert.escalate_at.is_not(None),
                Alert.escalate_at <= now,
            )
        )
        return (await self._session.scalars(query)).all()

    async def get_open_alerts_by_project(
        self, project_id: uuid.UUID, exclude_alert_id: uuid.UUID | None = None
    ) -> Sequence[Alert]:
        """ 
        Выбирает все оставшиеся открытые алерты проекта для честного пересчета светофора.
        """
        query = select(Alert).where(
            Alert.project_id == project_id,
            Alert.status == "OPEN",
        )
        if exclude_alert_id:
            query = query.where(Alert.id != exclude_alert_id)
        return (await self._session.scalars(query)).all()

    async def get_project_settings(self, project_id: uuid.UUID) -> SystemSetting | None:
        query = select(SystemSetting).where(SystemSetting.project_id == project_id)
        return await self._session.scalar(query)

    async def get_project_by_id(self, project_id: uuid.UUID) -> Project | None:
        return await self._session.get(Project, project_id)

    async def get_special_window_by_id(
        self, window_id: uuid.UUID
    ) -> SpecialStatusWindow | None:
        return await self._session.get(SpecialStatusWindow, window_id)

    async def get_active_special_window(
        self, project_id: uuid.UUID
    ) -> SpecialStatusWindow | None:
        query = select(SpecialStatusWindow).where(
            SpecialStatusWindow.project_id == project_id,
            SpecialStatusWindow.actual_end_time.is_(None),
        )
        return await self._session.scalar(query)

    async def list_orange_reports(
        self, project_id: uuid.UUID
    ) -> Sequence[OrangeStatusReport]:
        query = (
            select(OrangeStatusReport)
            .join(
                SpecialStatusWindow,
                SpecialStatusWindow.id == OrangeStatusReport.special_status_window_id,
            )
            .where(SpecialStatusWindow.project_id == project_id)
            .order_by(OrangeStatusReport.created_at.desc())
        )
        return (await self._session.scalars(query)).all()

    def add(self, entity) -> None:
        self._session.add(entity)