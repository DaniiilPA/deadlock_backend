import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class AlertTriggerRequest(BaseModel):
    project_id: uuid.UUID
    schedule_id: uuid.UUID | None = None
    severity: str = "YELLOW"  # "YELLOW" или "RED"
    trigger_type: str  # Гибкая строка (дефицит, простой, слепая зона и т.д.)
    trigger_frame_id: uuid.UUID | None = None
    details: dict[str, Any] | None = None
    escalation_hours: int | None = None  # null = не эскалировать, int = часы до RED


class AlertResolveRequest(BaseModel):
    action_taken: str  # "FALSE_ALARM", "PURPLE_STATUS", "ORANGE_STATUS"
    engineer_comment: str
    evidence_frame_ids: list[uuid.UUID] | None = None
    target_deadline: datetime | None = None


class AlertResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    schedule_id: uuid.UUID | None
    severity: str
    trigger_type: str
    status: str
    trigger_frame_id: uuid.UUID | None = None
    details: dict[str, Any] | None = None
    triggered_at: datetime
    escalate_at: datetime | None = None
    yellow_escalated_to_red_at: datetime | None = None
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AlertEscalationResponse(BaseModel):
    escalated_count: int
    escalated_alert_ids: list[uuid.UUID]