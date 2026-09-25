import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class ProjectTypeResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ProjectTypeCreate(BaseModel):
    code: str
    name: str
    description: str | None = None


class EquipmentTypeResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    ml_class_names: list[str]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class EquipmentTypeCreate(BaseModel):
    code: str
    name: str
    ml_class_names: list[str]


class StageTemplateResponse(BaseModel):
    id: uuid.UUID
    type_id: uuid.UUID
    stage_name: str
    substage_name: str
    sequence_order: int
    default_duration_days: int
    default_equipment: list[dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class SystemSettingsResponse(BaseModel):
    yellow_to_red_timeout_hours: int
    idle_threshold_minutes: int
    frame_retention_days: int

    model_config = ConfigDict(from_attributes=True)


class SystemSettingsUpdate(BaseModel):
    yellow_to_red_timeout_hours: int = 48
    idle_threshold_minutes: int = 30
    frame_retention_days: int = 7