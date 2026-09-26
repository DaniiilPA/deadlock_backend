import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidProjectStatusException,
    ProjectNotFoundException,
    ScheduleNotFoundException,
    TemplatesNotFoundException,
)
from app.core.utils import ensure_utc
from app.db.models import (
    AuditTrail,
    ProjectSchedule,
    StageEquipmentRequirement,
)
from app.repositories.schedule_repo import ScheduleRepository
from app.schemas import (
    CascadeShiftResponse,
    ScheduleStatusEnum,
    StageSyncItem,
)


class ScheduleService:
    def __init__(
        self,
        session: AsyncSession,
        schedule_repo: ScheduleRepository | None = None,
    ) -> None:
        self._session = session
        self._repo = schedule_repo or ScheduleRepository(session)

    async def apply_template(self, project_id: uuid.UUID, start_date: datetime) -> int:
        project = await self._repo.get_project_by_id(project_id)
        if not project:
            raise ProjectNotFoundException(project_id)

        if project.schedule_status != "DRAFT":
            raise InvalidProjectStatusException("Шаблон можно применить только к проекту в статусе DRAFT")

        templates = await self._repo.get_templates_by_type_id(project.type_id)
        if not templates:
            raise TemplatesNotFoundException("В справочнике нет этапов для данного типа стройки")

        # Очищаем старые этапы черновика, если они были
        await self._repo.delete_schedules_by_project_id(project_id)

        current_start = ensure_utc(start_date)
        created_count = 0

        for tmpl in templates:
            duration = timedelta(days=tmpl.default_duration_days)
            current_end = current_start + duration

            schedule = ProjectSchedule(
                project_id=project_id,
                stage_name=tmpl.stage_name,
                substage_name=tmpl.substage_name,
                sequence_order=tmpl.sequence_order,
                base_start_date=current_start,
                base_end_date=current_end,
                phantom_start_date=current_start,
                phantom_end_date=current_end,
                status=ScheduleStatusEnum.PLANNED.value,
            )
            self._repo.add(schedule)
            await self._session.flush()

            if tmpl.default_equipment:
                for eq_item in tmpl.default_equipment:
                    req = StageEquipmentRequirement(
                        schedule_id=schedule.id,
                        equipment_type=eq_item.get("equipment_type_code", eq_item.get("code")),
                        required_count=eq_item.get("default_count", eq_item.get("count", 1)),
                    )
                    self._repo.add(req)

            current_start = current_end
            created_count += 1

        await self._session.commit()
        return created_count

    async def get_schedules(self, project_id: uuid.UUID) -> list[ProjectSchedule]:
        project = await self._repo.get_project_by_id(project_id)
        if not project:
            raise ProjectNotFoundException(project_id)

        # Актуализируем статусы этапов по календарному времени перед отдачей
        await self.sync_stage_statuses(project_id)
        return await self._repo.get_schedules_by_project_id(project_id)

    async def sync_stage_statuses(self, project_id: uuid.UUID) -> None:
        """
        Автоматический переход этапов по времени:
        - Если время пришло (now >= base_start_date) и этап был PLANNED -> переводим в IN_PROGRESS
        - Если время вышло (now > base_end_date) и он все еще IN_PROGRESS -> DELAYED
        """
        schedules = await self._repo.get_schedules_by_project_id(project_id)
        now = datetime.now(timezone.utc)
        changed = False

        for s in schedules:
            if s.status == ScheduleStatusEnum.COMPLETED.value:
                continue

            start_dt = ensure_utc(s.base_start_date)
            end_dt = ensure_utc(s.base_end_date)

            if now >= start_dt and s.status == ScheduleStatusEnum.PLANNED.value:
                s.status = ScheduleStatusEnum.IN_PROGRESS.value
                s.actual_start_date = now
                changed = True
            elif now > end_dt and s.status == ScheduleStatusEnum.IN_PROGRESS.value:
                s.status = ScheduleStatusEnum.DELAYED.value
                changed = True

        if changed:
            await self._session.commit()

    async def get_current_stage_requirements(self, project_id: uuid.UUID) -> ProjectSchedule | None:
        """
        Эндпоинт-подсказка для ML-воркера: возвращает текущий активный этап и список требуемой техники
        """
        await self.sync_stage_statuses(project_id)
        schedules = await self._repo.get_schedules_by_project_id(project_id)

        current = next(
            (s for s in schedules if s.status in (ScheduleStatusEnum.IN_PROGRESS.value, ScheduleStatusEnum.DELAYED.value)),
            None,
        )
        if not current:
            current = next((s for s in schedules if s.status == ScheduleStatusEnum.PLANNED.value), None)

        return current

    async def start_stage_manually(self, schedule_id: uuid.UUID) -> ProjectSchedule:
        """Ручной старт этапа прорабом/инженером"""
        schedule = await self._repo.get_schedule_by_id(schedule_id)
        if not schedule:
            raise ScheduleNotFoundException(schedule_id)

        now = datetime.now(timezone.utc)
        schedule.status = ScheduleStatusEnum.IN_PROGRESS.value
        schedule.actual_start_date = now

        audit = AuditTrail(
            project_id=schedule.project_id,
            action_type="STAGE_STARTED_MANUALLY",
            new_values={"schedule_id": str(schedule.id), "started_at": now.isoformat()},
        )
        self._repo.add(audit)
        await self._session.commit()
        return schedule

    async def bulk_sync(self, project_id: uuid.UUID, stages_data: list[StageSyncItem]) -> None:
        project = await self._repo.get_project_by_id(project_id)
        if not project:
            raise ProjectNotFoundException(project_id)

        if project.schedule_status != "DRAFT":
            raise InvalidProjectStatusException("Редактировать график можно только в статусе DRAFT")

        for item in stages_data:
            if item.id:
                schedule = await self._repo.get_schedule_by_id(item.id)
                if schedule and schedule.project_id == project_id:
                    schedule.stage_name = item.stage_name
                    schedule.substage_name = item.substage_name
                    schedule.sequence_order = item.sequence_order
                    schedule.base_start_date = ensure_utc(item.base_start_date)
                    schedule.base_end_date = ensure_utc(item.base_end_date)
                    schedule.phantom_start_date = schedule.base_start_date
                    schedule.phantom_end_date = schedule.base_end_date
            else:
                schedule = ProjectSchedule(
                    project_id=project_id,
                    stage_name=item.stage_name,
                    substage_name=item.substage_name,
                    sequence_order=item.sequence_order,
                    base_start_date=ensure_utc(item.base_start_date),
                    base_end_date=ensure_utc(item.base_end_date),
                    phantom_start_date=ensure_utc(item.base_start_date),
                    phantom_end_date=ensure_utc(item.base_end_date),
                    status=ScheduleStatusEnum.PLANNED.value,
                )
                self._repo.add(schedule)
                await self._session.flush()

            # Обновление техники под этап
            await self._repo.delete_equipment_by_schedule_id(schedule.id)
            for eq in item.equipment_requirements:
                self._repo.add(
                    StageEquipmentRequirement(
                        schedule_id=schedule.id,
                        equipment_type=eq.equipment_type,
                        required_count=eq.required_count,
                    )
                )

        await self._session.commit()

    async def confirm_schedule(self, project_id: uuid.UUID) -> None:
        project = await self._repo.get_project_by_id(project_id)
        if not project:
            raise ProjectNotFoundException(project_id)

        project.schedule_status = "ACTIVE"
        project.status = "ACTIVE"
        await self._session.commit()

    async def complete_stage_early(
        self, schedule_id: uuid.UUID, actual_end_date: datetime, foreman_comment: str
    ) -> ProjectSchedule:
        schedule = await self._repo.get_schedule_by_id(schedule_id)
        if not schedule:
            raise ScheduleNotFoundException(schedule_id)

        schedule.status = ScheduleStatusEnum.COMPLETED.value
        schedule.actual_end_date = ensure_utc(actual_end_date)

        audit = AuditTrail(
            project_id=schedule.project_id,
            action_type="STAGE_COMPLETED_EARLY",
            new_values={
                "schedule_id": str(schedule.id),
                "substage_name": schedule.substage_name,
                "actual_end_date": schedule.actual_end_date.isoformat(),
                "comment": foreman_comment,
            },
        )
        self._repo.add(audit)
        await self._session.commit()
        return schedule

    async def cascade_shift(
        self,
        project_id: uuid.UUID,
        from_schedule_id: uuid.UUID,
        shift_days: int,
        target_timeline: str,
        reason_comment: str,
        document_reference: str | None,
        close_special_status: bool,
        user_id: uuid.UUID | None,
    ) -> CascadeShiftResponse:
        pivot_stage = await self._repo.get_schedule_by_id(from_schedule_id)
        if not pivot_stage or pivot_stage.project_id != project_id:
            raise ScheduleNotFoundException(from_schedule_id)

        stages_to_shift = await self._repo.get_uncompleted_subsequent_stages(
            project_id=project_id, min_sequence=pivot_stage.sequence_order
        )
        if not stages_to_shift:
            raise InvalidProjectStatusException("Нет незавершенных этапов для сдвига")

        shift_delta = timedelta(days=shift_days)

        for stage in stages_to_shift:
            if target_timeline == "BASE":
                stage.base_start_date += shift_delta
                stage.base_end_date += shift_delta
            else:  # PHANTOM
                base_start = stage.phantom_start_date or stage.base_start_date
                base_end = stage.phantom_end_date or stage.base_end_date
                stage.phantom_start_date = base_start + shift_delta
                stage.phantom_end_date = base_end + shift_delta

        if close_special_status:
            project = await self._repo.get_project_by_id(project_id)
            if project:
                project.current_special_status = "NONE"

            active_window = await self._repo.get_active_special_window(project_id)
            if active_window:
                active_window.actual_end_time = datetime.now(timezone.utc)
                active_window.close_comment = (
                    f"Сдвиг сроков выполнен на {shift_days} дн. Документ: {document_reference or 'б/н'}"
                )

        last_stage = stages_to_shift[-1]
        audit = AuditTrail(
            project_id=project_id,
            user_id=user_id,
            action_type="CASCADE_SHIFT",
            old_values={"shift_days": 0},
            new_values={
                "shift_days": shift_days,
                "target_timeline": target_timeline,
                "reason": reason_comment,
                "document": document_reference,
            },
        )
        self._repo.add(audit)
        await self._session.commit()

        new_end = last_stage.phantom_end_date or last_stage.base_end_date
        old_end = new_end - shift_delta

        return CascadeShiftResponse(
            shifted_stages_count=len(stages_to_shift),
            old_estimated_completion=old_end,
            new_estimated_completion=new_end,
            audit_trail_id=audit.id,
        )