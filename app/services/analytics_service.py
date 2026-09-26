import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProjectNotFoundException
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
        Главный эндпоинт шапки объекта. Рассчитывает все ключевые KPI для фронта.
        """
        project = await self._repo.get_project_for_summary(project_id)
        if not project:
            raise ProjectNotFoundException(project_id)

        now = datetime.now(timezone.utc)
        schedules = sorted(project.schedules, key=lambda s: s.sequence_order)

        # Расчет двух формул прогресса
        total_duration_sec = 0.0
        completed_duration_sec = 0.0
        current_stage: LiveSummaryStage | None = None

        for s in schedules:
            stage_duration = (s.base_end_date - s.base_start_date).total_seconds()
            total_duration_sec += stage_duration

            if s.status == "COMPLETED":
                completed_duration_sec += stage_duration
            elif not current_stage and s.status in ("IN_PROGRESS", "PLANNED"):
                # Текущий рабочий этап
                days_total = max(int(stage_duration // 86400), 1)

                if now < s.base_start_date:
                    days_current = 0
                else:
                    days_current = min(
                        int((now - s.base_start_date).total_seconds() // 86400) + 1,
                        days_total,
                    )

                days_remaining = max(
                    int((s.base_end_date - now).total_seconds() // 86400), 0
                )

                # Определение статуса темпа
                if now > s.base_end_date:
                    progress_status = "BEHIND_SCHEDULE"
                elif days_current > 0 and days_remaining > 0:
                    progress_status = "ON_SCHEDULE"
                else:
                    progress_status = "ON_SCHEDULE"

                current_stage = LiveSummaryStage(
                    name=s.substage_name,
                    days_current=days_current,
                    days_total_stage=days_total,
                    days_remaining=days_remaining,
                    progress_status=progress_status,
                )

        physical_progress = (
            round((completed_duration_sec / total_duration_sec) * 100, 1)
            if total_duration_sec > 0
            else 0.0
        )

        time_elapsed = 0.0
        if schedules:
            first_start = schedules[0].base_start_date
            last_end = schedules[-1].base_end_date
            total_span = (last_end - first_start).total_seconds()
            if total_span > 0 and now > first_start:
                spent = (now - first_start).total_seconds()
                time_elapsed = round(min(max(spent / total_span, 0.0), 1.0) * 100, 1)

        # Cчетчик техники прямо сейчас (Факт / План)
        latest_interval = await self._repo.get_latest_interval_analytics(project_id)
        equipment_realtime = LiveSummaryEquipment(
            required_total=0,
            detected_total=0,
            active_count=0,
            idle_count=0,
        )

        if latest_interval and isinstance(latest_interval.equipment_summary, dict):
            summary = latest_interval.equipment_summary
            active_items = summary.get("detected_active", [])
            idle_items = summary.get("detected_idle", [])
            required_items = summary.get("required", [])

            active_cnt = sum(item.get("count", 1) for item in active_items)
            idle_cnt = sum(item.get("count", 1) for item in idle_items)
            req_cnt = sum(item.get("count", 1) for item in required_items)

            equipment_realtime = LiveSummaryEquipment(
                required_total=req_cnt,
                detected_total=active_cnt + idle_cnt,
                active_count=active_cnt,
                idle_count=idle_cnt,
            )
        elif current_stage:
            # Если снимков еще нет - показываем плановую потребность текущего этапа
            active_sched = next(
                (s for s in schedules if s.substage_name == current_stage.name), None
            )
            if active_sched:
                req_cnt = sum(r.required_count for r in active_sched.equipment_requirements)
                equipment_realtime.required_total = req_cnt

        # Дедлайн активного спецстатуса (для таймера на фронтенде)
        special_window = await self._repo.get_active_special_status_window(project_id)
        special_deadline = special_window.target_deadline if special_window else None

        return LiveSummaryResponse(
            project_name=project.name,
            physical_progress_percent=physical_progress,
            time_elapsed_percent=time_elapsed,
            alert_level=project.current_alert_level,
            special_status=project.current_special_status,
            special_status_deadline=special_deadline,
            current_stage=current_stage,
            equipment_realtime=equipment_realtime,
        )

    async def get_department_overview(self) -> DepartmentOverviewResponse:
        """Сводные показатели по всем стройкам города для экрана мэрии"""
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