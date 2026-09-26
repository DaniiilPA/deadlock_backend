import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DomainException,
    EntityNotFoundException,
    ProjectNotFoundException,
)
from app.core.utils import ensure_utc
from app.db.models import (
    Alert,
    AlertResolution,
    AuditTrail,
    OrangeStatusReport,
    Project,
    SpecialStatusWindow,
    User,
)
from app.repositories.alert_repo import AlertRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas import AlertResolveRequest, AlertTriggerRequest


class AlertService:
    def __init__(
        self,
        session: AsyncSession,
        alert_repo: AlertRepository | None = None,
        project_repo: ProjectRepository | None = None,
    ) -> None:
        self._session = session
        self._repo = alert_repo or AlertRepository(session)
        self._project_repo = project_repo or ProjectRepository(session)

    async def _check_engineer_permission(self, project_id: uuid.UUID, user: User) -> None:
        if "admin" in user.roles:
            return
        project = await self._project_repo.get_by_id(project_id)
        if project and project.creator_id == user.id:
            return
        assignment = await self._project_repo.get_assignment(project_id, user.id)
        if not assignment or assignment.role_in_project != "engineer":
            raise DomainException(
                message="Недостаточно прав. Вы не назначены инженером на данный объект строительства",
                status_code=403,
            )

    async def _recalculate_project_alert_level(
        self, project: Project, exclude_alert_id: uuid.UUID | None = None
    ) -> None:
        remaining = await self._repo.get_open_alerts_by_project(
            project_id=project.id, exclude_alert_id=exclude_alert_id
        )
        if any(a.severity == "RED" for a in remaining):
            project.current_alert_level = "RED"
        elif any(a.severity == "YELLOW" for a in remaining):
            project.current_alert_level = "YELLOW"
        else:
            project.current_alert_level = "GREEN"
            project.yellow_alert_started_at = None

    async def trigger_alert(self, data: AlertTriggerRequest) -> Alert:
        project = await self._repo.get_project_by_id(data.project_id)
        if not project:
            raise ProjectNotFoundException(data.project_id)

        now = datetime.now(timezone.utc)
        active_window = await self._repo.get_active_special_window(data.project_id)
        if active_window and ensure_utc(active_window.target_deadline) <= now:
            project.current_special_status = "NONE"
            active_window.actual_end_time = now
            active_window.close_comment = "Срок дедлайна истек. Режим снят автоматически."
            await self._recalculate_project_alert_level(project)
            active_window = None

        existing = await self._repo.get_open_alert_by_trigger(
            project_id=data.project_id,
            schedule_id=data.schedule_id,
            trigger_type=data.trigger_type,
        )
        if existing:
            return existing

        escalate_at = None
        if data.severity == "YELLOW" and data.escalation_hours is not None:
            escalate_at = now + timedelta(hours=data.escalation_hours)

        alert_details = data.details or {}
        if project.current_special_status in ("PURPLE", "ORANGE"):
            alert_details["recorded_during_special_status"] = project.current_special_status

        alert = Alert(
            project_id=data.project_id,
            schedule_id=data.schedule_id,
            severity=data.severity,
            trigger_type=data.trigger_type,
            status="OPEN",
            triggered_at=now,
            escalate_at=escalate_at,
            trigger_frame_id=data.trigger_frame_id,
            details=alert_details,
        )
        self._repo.add(alert)

        if project.current_special_status in ("PURPLE", "ORANGE"):
            pass
        else:
            if data.severity == "RED":
                project.current_alert_level = "RED"
            elif data.severity == "YELLOW" and project.current_alert_level != "RED":
                project.current_alert_level = "YELLOW"
                if not project.yellow_alert_started_at:
                    project.yellow_alert_started_at = now

        await self._session.commit()
        return alert

    async def check_and_escalate_alerts(self) -> list[uuid.UUID]:
        now = datetime.now(timezone.utc)
        alerts_to_escalate = await self._repo.get_alerts_ready_to_escalate(now)
        escalated_ids: list[uuid.UUID] = []

        for alert in alerts_to_escalate:
            alert.severity = "RED"
            alert.yellow_escalated_to_red_at = now

            project = alert.project
            if project and project.current_special_status not in ("PURPLE", "ORANGE"):
                project.current_alert_level = "RED"

            audit = AuditTrail(
                project_id=alert.project_id,
                action_type="YELLOW_ESCALATED_TO_RED",
                new_values={
                    "alert_id": str(alert.id),
                    "trigger_type": alert.trigger_type,
                    "escalated_at": now.isoformat(),
                },
            )
            self._repo.add(audit)
            escalated_ids.append(alert.id)

        if escalated_ids:
            await self._session.commit()

        return escalated_ids

    async def resolve_alert(
        self,
        alert_id: uuid.UUID,
        current_user: User,
        data: AlertResolveRequest,
    ) -> Alert:
        alert = await self._repo.get_alert_by_id(alert_id)
        if not alert:
            raise EntityNotFoundException("Алерт не найден")

        await self._check_engineer_permission(alert.project_id, current_user)

        if alert.status != "OPEN":
            raise DomainException("Алерт уже закрыт")

        project = alert.project or await self._repo.get_project_by_id(alert.project_id)
        if not project:
            raise ProjectNotFoundException(alert.project_id)

        now = datetime.now(timezone.utc)

        resolution = AlertResolution(
            alert_id=alert.id,
            engineer_id=current_user.id,
            action_taken=data.action_taken,
            engineer_comment=data.engineer_comment,
            evidence_frame_ids=data.evidence_frame_ids,
            resolved_at=now,
        )
        self._repo.add(resolution)

        alert.status = "RESOLVED"
        alert.resolved_at = now

        if data.action_taken == "FALSE_ALARM":
            await self._recalculate_project_alert_level(project, exclude_alert_id=alert.id)

        elif data.action_taken in ("PURPLE_STATUS", "ORANGE_STATUS"):
            if not data.target_deadline:
                raise DomainException(
                    "Для специального статуса необходимо указать дедлайн (target_deadline)"
                )

            old_window = await self._repo.get_active_special_window(project.id)
            if old_window:
                old_window.actual_end_time = now
                old_window.close_comment = "Закрыто автоматически при назначении нового спецстатуса"

            status_type = "PURPLE" if data.action_taken == "PURPLE_STATUS" else "ORANGE"
            project.current_special_status = status_type
            project.current_alert_level = "GREEN"

            window = SpecialStatusWindow(
                project_id=project.id,
                alert_id=alert.id,
                type=status_type,
                created_by_user_id=current_user.id,
                start_time=now,
                target_deadline=data.target_deadline,
                reason_comment=data.engineer_comment,
                close_comment=None,
            )
            self._repo.add(window)

        audit = AuditTrail(
            project_id=project.id,
            user_id=current_user.id,
            action_type="ALERT_RESOLVED",
            new_values={
                "alert_id": str(alert.id),
                "action_taken": data.action_taken,
                "comment": data.engineer_comment,
            },
        )
        self._repo.add(audit)

        await self._session.commit()
        return alert

    async def close_special_status(
        self, window_id: uuid.UUID, current_user: User, close_comment: str
    ) -> SpecialStatusWindow:
        window = await self._repo.get_special_window_by_id(window_id)
        if not window:
            raise EntityNotFoundException("Окно специального статуса не найдено")

        await self._check_engineer_permission(window.project_id, current_user)

        if window.actual_end_time is not None:
            raise DomainException("Специальный статус уже закрыт")

        now = datetime.now(timezone.utc)
        window.actual_end_time = now
        window.close_comment = close_comment

        project = await self._repo.get_project_by_id(window.project_id)
        if project:
            project.current_special_status = "NONE"
            await self._recalculate_project_alert_level(project)

        audit = AuditTrail(
            project_id=window.project_id,
            user_id=current_user.id,
            action_type="SPECIAL_STATUS_CLOSED",
            new_values={
                "window_id": str(window.id),
                "close_comment": close_comment,
            },
        )
        self._repo.add(audit)
        await self._session.commit()
        return window

    async def create_orange_report(
        self,
        window_id: uuid.UUID,
        current_user: User,
        is_plan_caught_up: bool,
        time_lost_hours: Decimal,
        responsible_party: str | None,
        summary_meta: dict[str, Any],
    ) -> OrangeStatusReport:
        window = await self._repo.get_special_window_by_id(window_id)
        if not window:
            raise EntityNotFoundException("Окно специального статуса не найдено")

        await self._check_engineer_permission(window.project_id, current_user)

        if window.type != "ORANGE":
            raise DomainException("Отчет разбора составляется только для оранжевого статуса")

        report = OrangeStatusReport(
            special_status_window_id=window.id,
            is_plan_caught_up=is_plan_caught_up,
            time_lost_hours=time_lost_hours,
            responsible_party=responsible_party,
            summary_meta=summary_meta,
        )
        self._repo.add(report)

        audit = AuditTrail(
            project_id=window.project_id,
            user_id=current_user.id,
            action_type="ORANGE_REPORT_CREATED",
            new_values={
                "window_id": str(window.id),
                "is_plan_caught_up": is_plan_caught_up,
                "time_lost_hours": float(time_lost_hours),
                "responsible_party": responsible_party,
            },
        )
        self._repo.add(audit)

        await self._session.commit()
        return report

    async def list_alerts(
        self,
        current_user: User,
        project_id: uuid.UUID | None = None,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Alert]:
        if "admin" not in current_user.roles:
            if not project_id:
                raise DomainException(
                    message="Параметр project_id обязателен для сотрудников объекта",
                    status_code=400,
                )
            assignment = await self._project_repo.get_assignment(project_id, current_user.id)
            if not assignment:
                raise DomainException(
                    message="Вы не назначены на данный объект строительства",
                    status_code=403,
                )

        return list(
            await self._repo.list_alerts(
                project_id=project_id,
                severity=severity,
                status=status,
                limit=limit,
                offset=offset,
            )
        )

    async def get_active_alert(self, project_id: uuid.UUID, current_user: User) -> Alert | None:
        if "admin" not in current_user.roles:
            assignment = await self._project_repo.get_assignment(project_id, current_user.id)
            if not assignment:
                raise DomainException("Вы не назначены на данный объект строительства", status_code=403)

        return await self._repo.get_active_alert_by_project(project_id)

    async def get_current_special_status(
        self, project_id: uuid.UUID
    ) -> SpecialStatusWindow | None:
        await self._repo.get_project_by_id(project_id)
        return await self._repo.get_active_special_window(project_id)

    async def list_orange_reports(
        self, project_id: uuid.UUID
    ) -> list[OrangeStatusReport]:
        return list(await self._repo.list_orange_reports(project_id))
    
    async def check_and_expire_special_statuses(self) -> list[uuid.UUID]:
        now = datetime.now(timezone.utc)
        expired_windows = await self._repo.get_expired_special_windows(now)
        expired_ids: list[uuid.UUID] = []

        for window in expired_windows:
            window.actual_end_time = now
            window.close_comment = "Срок дедлайна истек. Режим снят автоматически планировщиком."

            project = window.project
            if project and project.current_special_status == window.type:
                project.current_special_status = "NONE"
                await self._recalculate_project_alert_level(project)

            audit = AuditTrail(
                project_id=window.project_id,
                action_type="SPECIAL_STATUS_EXPIRED",
                new_values={
                    "window_id": str(window.id),
                    "type": window.type,
                    "expired_at": now.isoformat(),
                },
            )
            self._repo.add(audit)
            expired_ids.append(window.id)

        if expired_ids:
            await self._session.commit()

        return expired_ids