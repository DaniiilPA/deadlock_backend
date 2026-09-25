import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    address: str
    type_id: uuid.UUID


class ProjectUpdate(BaseModel):
    name: str | None = None
    address: str | None = None


class ProjectAssignmentCreate(BaseModel):
    user_id: uuid.UUID
    role_in_project: str  # "foreman" или "engineer"


class ProjectAssignmentResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    role_in_project: str
    assigned_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    type_id: uuid.UUID
    creator_id: uuid.UUID
    status: str
    schedule_status: str
    current_alert_level: str
    current_special_status: str
    yellow_alert_started_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectListItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    type_id: uuid.UUID
    status: str
    schedule_status: str
    current_alert_level: str
    current_special_status: str
    # Расчетные поля для таблицы Департамента:
    current_stage_name: str | None = None
    physical_progress_percent: float = 0.0  # По закрытым этапам
    time_elapsed_percent: float = 0.0       # По календарю
    critical_alerts_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)