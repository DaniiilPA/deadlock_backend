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
from app.db.models import (
    Alert,
    AlertResolution,
    AuditTrail,
    OrangeStatusReport,
    Project,
    SpecialStatusWindow,
)
from app.repositories.alert_repo import AlertRepository
from app.schemas import AlertResolveRequest, AlertTriggerRequest


class AlertService:
    def __init__(
        self,
        session: AsyncSession,
        alert_repo: AlertRepository | None = None,
    ) -> None:
        self._session = session
        self._repo = alert_repo or AlertRepository(session)

    async def trigger_alert(self, data: AlertTriggerRequest) -> Alert:
        """
        Фиксация инцидента воркером или алгоритмом.
        Если data.escalation_hours is None -> алерт НИКОГДА не перейдет в RED (escalate_at = None).
        """
        project = await self._repo.get_project_by_id(data.project_id)
        if not project:
            raise ProjectNotFoundException(data.project_id)

        # Защита от дублей (учитывает случай schedule_id IS NULL)
        existing = await self._repo.get_open_alert_by_trigger(
            project_id=data.project_id,
            schedule_id=data.schedule_id,
            trigger_type=data.trigger_type,
        )
        if existing:
            return existing

        now = datetime.now(timezone.utc)

        # Расчет времени эскалации (полностью контролируется вызывающей стороной)
        escalate_at = None
        if data.severity == "YELLOW" and data.escalation_hours is not None:
            escalate_at = now + timedelta(hours=data.escalation_hours)

        alert = Alert(
            project_id=data.project_id,
            schedule_id=data.schedule_id,
            severity=data.severity,
            trigger_type=data.trigger_type,
            status="OPEN",
            triggered_at=now,
            escalate_at=escalate_at,
            trigger_frame_id=data.trigger_frame_id,
            details=data.details,
        )
        self._repo.add(alert)

        # Обновление светофора объекта
        if data.severity == "RED":
            project.current_alert_level = "RED"
        elif data.severity == "YELLOW" and project.current_alert_level != "RED":
            project.current_alert_level = "YELLOW"
            if not project.yellow_alert_started_at:
                project.yellow_alert_started_at = now

        await self._session.commit()
        return alert

    async def check_and_escalate_alerts(self) -> list[uuid.UUID]:
        """
        Инструмент для фонового воркера:
        Находит все открытые YELLOW алерты, у которых наступил escalate_at,
        и переводит их в RED (проект подгружен через joinedload, N+1 исключен).
        """
        now = datetime.now(timezone.utc)
        alerts_to_escalate = await self._repo.get_alerts_ready_to_escalate(now)
        escalated_ids: list[uuid.UUID] = []

        for alert in alerts_to_escalate:
            alert.severity = "RED"
            alert.yellow_escalated_to_red_at = now

            project = alert.project
            if project:
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
        engineer_id: uuid.UUID,
        data: AlertResolveRequest,
    ) -> Alert:
        """
        Решение инженера по красному алерту (3 регламентных пути):
        1. FALSE_ALARM   -> ложная тревога (честный пересчет оставшихся открытых алертов).
        2. PURPLE_STATUS -> ввод режима ожидания документов (окно SpecialStatusWindow).
        3. ORANGE_STATUS -> ввод режима нагона плана (окно SpecialStatusWindow).
        """
        alert = await self._repo.get_alert_by_id(alert_id)
        if not alert:
            raise EntityNotFoundException("Алерт не найден")

        if alert.status != "OPEN":
            raise DomainException("Алерт уже закрыт")

        project = alert.project or await self._repo.get_project_by_id(alert.project_id)
        if not project:
            raise ProjectNotFoundException(alert.project_id)

        now = datetime.now(timezone.utc)

        # Фиксация решения инженера
        resolution = AlertResolution(
            alert_id=alert.id,
            engineer_id=engineer_id,
            action_taken=data.action_taken,
            engineer_comment=data.engineer_comment,
            evidence_frame_ids=data.evidence_frame_ids,
            resolved_at=now,
        )
        self._repo.add(resolution)

        alert.status = "RESOLVED"
        alert.resolved_at = now

        # Обработка сценариев
        if data.action_taken == "FALSE_ALARM":
            remaining = await self._repo.get_open_alerts_by_project(
                project_id=project.id, exclude_alert_id=alert.id
            )
            if any(a.severity == "RED" for a in remaining):
                project.current_alert_level = "RED"
            elif any(a.severity == "YELLOW" for a in remaining):
                project.current_alert_level = "YELLOW"
            else:
                project.current_alert_level = "GREEN"
                project.yellow_alert_started_at = None

        elif data.action_taken in ("PURPLE_STATUS", "ORANGE_STATUS"):
            if not data.target_deadline:
                raise DomainException(
                    "Для специального статуса необходимо указать дедлайн (target_deadline)"
                )

            status_type = "PURPLE" if data.action_taken == "PURPLE_STATUS" else "ORANGE"
            project.current_special_status = status_type
            project.current_alert_level = "GREEN"  # Тревога снята, проект перешел в спецрежим

            window = SpecialStatusWindow(
                project_id=project.id,
                alert_id=alert.id,
                type=status_type,
                created_by_user_id=engineer_id,
                start_time=now,
                target_deadline=data.target_deadline,
                reason_comment=data.engineer_comment,
                close_comment=None,
            )
            self._repo.add(window)

        # Запись в аудит
        audit = AuditTrail(
            project_id=project.id,
            user_id=engineer_id,
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

    async def list_alerts(
        self,
        project_id: uuid.UUID | None = None,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Alert]:
        return list(
            await self._repo.list_alerts(
                project_id=project_id,
                severity=severity,
                status=status,
                limit=limit,
                offset=offset,
            )
        )

    async def get_active_alert(self, project_id: uuid.UUID) -> Alert | None:
        return await self._repo.get_active_alert_by_project(project_id)

    async def get_current_special_status(
        self, project_id: uuid.UUID
    ) -> SpecialStatusWindow | None:
        await self._repo.get_project_by_id(project_id)
        return await self._repo.get_active_special_window(project_id)

    async def close_special_status(
        self, window_id: uuid.UUID, engineer_id: uuid.UUID, close_comment: str
    ) -> SpecialStatusWindow:
        """Инженер вручную закрывает окно специального статуса"""
        window = await self._repo.get_special_window_by_id(window_id)
        if not window:
            raise EntityNotFoundException("Окно специального статуса не найдено")

        if window.actual_end_time is not None:
            raise DomainException("Специальный статус уже закрыт")

        now = datetime.now(timezone.utc)
        window.actual_end_time = now
        window.close_comment = close_comment

        project = await self._repo.get_project_by_id(window.project_id)
        if project:
            project.current_special_status = "NONE"

        audit = AuditTrail(
            project_id=window.project_id,
            user_id=engineer_id,
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
        engineer_id: uuid.UUID,
        is_plan_caught_up: bool,
        time_lost_hours: Decimal,
        responsible_party: str | None,
        summary_meta: dict[str, Any],
    ) -> OrangeStatusReport:
        """
        Инженер сохраняет результаты разбора полетов (Post-Mortem) по оранжевому статусу.
        Сервис просто фиксирует факт отчета и аудит, не производя скрытых переключений статуса.
        """
        window = await self._repo.get_special_window_by_id(window_id)
        if not window:
            raise EntityNotFoundException("Окно специального статуса не найдено")

        if window.type != "ORANGE":
            raise DomainException("Отчет разбора составляется только для оранжевого статуса")

        # Сохраняем отчет разбора
        report = OrangeStatusReport(
            special_status_window_id=window.id,
            is_plan_caught_up=is_plan_caught_up,
            time_lost_hours=time_lost_hours,
            responsible_party=responsible_party,
            summary_meta=summary_meta,
        )
        self._repo.add(report)

        # Логируем действие в аудит
        audit = AuditTrail(
            project_id=window.project_id,
            user_id=engineer_id,
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

    async def list_orange_reports(
        self, project_id: uuid.UUID
    ) -> list[OrangeStatusReport]:
        return list(await self._repo.list_orange_reports(project_id))