from datetime import datetime, timezone


def ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def calculate_project_progress(schedules: list, now: datetime) -> tuple[float, float]:
    if not schedules:
        return 0.0, 0.0

    total_planned_seconds = 0.0
    completed_seconds = 0.0
    current_stage_contributed_seconds = 0.0

    for s in schedules:
        start = ensure_utc(s.base_start_date)
        end = ensure_utc(s.base_end_date)
        duration = max((end - start).total_seconds(), 0.0)
        total_planned_seconds += duration

        if s.status == "COMPLETED":
            completed_seconds += duration
        elif s.status in ("IN_PROGRESS", "DELAYED") and current_stage_contributed_seconds == 0.0:
            if now > start:
                spent = (now - start).total_seconds()
                current_stage_contributed_seconds = max(min(spent, duration * 0.95), 0.0)

    if total_planned_seconds == 0.0:
        return 0.0, 0.0

    earned_seconds = completed_seconds + current_stage_contributed_seconds
    physical_progress = round(min((earned_seconds / total_planned_seconds) * 100.0, 100.0), 1)

    first_start = ensure_utc(schedules[0].base_start_date)
    last_end = ensure_utc(schedules[-1].base_end_date)
    calendar_total = max((last_end - first_start).total_seconds(), 0.0)

    time_elapsed = 0.0
    if calendar_total > 0.0 and now > first_start:
        spent_calendar = (now - first_start).total_seconds()
        time_elapsed = round((spent_calendar / calendar_total) * 100.0, 1)

    return physical_progress, time_elapsed