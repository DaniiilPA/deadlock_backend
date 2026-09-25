import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class LiveSummaryStage(BaseModel):
    name: str
    days_current: int       # День 14
    days_total_stage: int   # из 20
    days_remaining: int     # осталось 6
    progress_status: str    # "ON_SCHEDULE", "BEHIND_SCHEDULE", "AHEAD_OF_SCHEDULE"


class LiveSummaryEquipment(BaseModel):
    required_total: int
    detected_total: int
    active_count: int
    idle_count: int


class LiveSummaryResponse(BaseModel):
    project_name: str
    physical_progress_percent: float  # Реальная готовность по закрытым этапам
    time_elapsed_percent: float       # Прошедшее время по календарю
    alert_level: str
    special_status: str
    special_status_deadline: datetime | None = None
    current_stage: LiveSummaryStage | None = None
    equipment_realtime: LiveSummaryEquipment


class DepartmentOverviewResponse(BaseModel):
    total_projects: int
    green_count: int
    yellow_count: int
    red_count: int
    purple_count: int
    orange_count: int
    total_idle_hours: float
    critical_contractors: list[dict[str, Any]] = []


class AuditTrailResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID | None
    user_email: str | None = None
    action_type: str
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)