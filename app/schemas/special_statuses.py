import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict


class SpecialStatusCloseRequest(BaseModel):
    close_comment: str  # Обязательно при закрытии


class SpecialStatusResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    alert_id: uuid.UUID
    type: str  # "PURPLE" или "ORANGE"
    created_by_user_id: uuid.UUID
    start_time: datetime
    target_deadline: datetime
    actual_end_time: datetime | None = None
    reason_comment: str
    close_comment: str | None = None  # Опционально (при открытии окна здесь NULL)

    model_config = ConfigDict(from_attributes=True)


class OrangeStatusReportCreate(BaseModel):
    is_plan_caught_up: bool
    time_lost_hours: Decimal
    responsible_party: str | None = None
    summary_meta: dict[str, Any] = {}


class OrangeStatusReportResponse(BaseModel):
    id: uuid.UUID
    special_status_window_id: uuid.UUID
    is_plan_caught_up: bool
    time_lost_hours: Decimal
    responsible_party: str | None
    summary_meta: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)