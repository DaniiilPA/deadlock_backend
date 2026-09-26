import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProjectNotFoundException
from app.core.utils import calculate_project_progress, ensure_utc
from app.db.models import ProjectSchedule
from app.repositories.analytics_repo import AnalyticsRepository
from app.schemas.analytics import (
    AuditTrailResponse,
    DepartmentOverviewResponse,
    LiveSummaryEquipment,
    LiveSummaryResponse,
    LiveSummaryStage,
)


class AnalyticsService:
    def __init__(
        self,
        session: AsyncSession,
        analytics_repo: AnalyticsRepository | None = None,
    ) -> None:
        self._session = session
        self._repo = analytics_repo or AnalyticsRepository(session)

    async def get_live_summary(self, project_id: uuid.UUID) -> LiveSummaryResponse:
        """
        Главная шапка дашборда объекта:
        - Расчет двух шкал прогресса через calculate_project_progress (факт выполнения vs календарное время)
        - Карточка текущего этапа и его темпа
        - Мгновенная сводка по технике со всех камер из последней записи воркера
        - Статус светофора и спецстатуса
        """
        project = await self._repo.get_project_for_summary(project_id)
        if not project:
            raise ProjectNotFoundException(project_id)

        now = datetime.now(timezone.utc)
        schedules: list[ProjectSchedule] = sorted(project.schedules, key=lambda s: s.sequence_order)

        # Расчет прогресса (Физический + Календарный) через функцию из utils.py
        physical_progress, time_elapsed = calculate_project_progress(schedules, now)

        # Поиск текущего этапа
        current_sched: ProjectSchedule | None = None
        for s in schedules:
            if s.status != "COMPLETED":
                current_sched = s
                break

        current_stage_dto: LiveSummaryStage | None = None
        if current_sched:
            c_start = ensure_utc(current_sched.base_start_date)
            c_end = ensure_utc(current_sched.base_end_date)
            c_duration = max((c_end - c_start).total_seconds(), 1.0)
            days_total = max(int(c_duration // 86400), 1)

            if now < c_start:
                progress_status = "NOT_STARTED"
                days_current = 0
                days_remaining = days_total
            elif now > c_end:
                progress_status = "BEHIND_SCHEDULE"
                days_current = days_total
                days_remaining = 0
            else:
                progress_status = "ON_SCHEDULE"
                days_current = max(int((now - c_start).total_seconds() // 86400) + 1, 1)
                days_remaining = max(int((c_end - now).total_seconds() // 86400), 0)

            current_stage_dto = LiveSummaryStage(
                name=current_sched.substage_name,
                days_current=days_current,
                days_total_stage=days_total,
                days_remaining=days_remaining,
                progress_status=progress_status,
            )

        # Сводка по технике (читаем плоские поля последней интервальной записи от воркера)
        latest_intervals = await self._repo.get_latest_intervals_per_camera(project_id)
        active_sum = sum(i.active_equipment_count for i in latest_intervals)
        idle_sum = sum(i.idle_equipment_count for i in latest_intervals)

        # План берем из требований текущего этапа, либо из сводки воркера
        req_count = 0
        if current_sched:
            req_count = sum(r.required_count for r in current_sched.equipment_requirements)
        elif latest_intervals:
            req_count = latest_intervals[0].required_equipment_count

        equipment_realtime = LiveSummaryEquipment(
            required_total=req_count,
            detected_total=active_sum + idle_sum,
            active_count=active_sum,
            idle_count=idle_sum,
        )

        # Дедлайн активного спецстатуса
        special_window = await self._repo.get_active_special_status_window(project_id)
        special_deadline = (
            ensure_utc(special_window.target_deadline) if special_window else None
        )

        return LiveSummaryResponse(
            project_name=project.name,
            physical_progress_percent=physical_progress,
            time_elapsed_percent=time_elapsed,
            alert_level=project.current_alert_level,
            special_status=project.current_special_status,
            special_status_deadline=special_deadline,
            current_stage=current_stage_dto,
            equipment_realtime=equipment_realtime,
        )

    async def get_department_overview(self) -> DepartmentOverviewResponse:
        """Сводная макро-статистика для экрана Департамента / Мэрии"""
        counts = await self._repo.get_department_counts()
        total_lost_hours = await self._repo.get_total_time_lost_hours()

        return DepartmentOverviewResponse(
            total_projects=counts["total_projects"],
            green_count=counts["green_count"],
            yellow_count=counts["yellow_count"],
            red_count=counts["red_count"],
            purple_count=counts["purple_count"],
            orange_count=counts["orange_count"],
            total_idle_hours=total_lost_hours,
            critical_contractors=[],
        )

    async def get_audit_trail(
        self,
        project_id: uuid.UUID,
        action_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditTrailResponse]:
        """Журнал юридически значимых действий по объекту"""
        rows = await self._repo.get_audit_trail(
            project_id=project_id,
            action_type=action_type,
            limit=limit,
            offset=offset,
        )
        return [
            AuditTrailResponse(
                id=audit.id,
                project_id=audit.project_id,
                user_id=audit.user_id,
                user_email=email,
                action_type=audit.action_type,
                old_values=audit.old_values,
                new_values=audit.new_values,
                created_at=audit.created_at,
            )
            for audit, email in rows
        ]