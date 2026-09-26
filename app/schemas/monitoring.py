import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class CameraCreate(BaseModel):
    stream_url: str


class CameraUpdate(BaseModel):
    stream_url: str | None = None
    is_active: bool | None = None


class CameraResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    stream_url: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FrameAnalysisCreate(BaseModel):
    captured_at: datetime
    image_path: str
    detection_result: dict[str, Any] | None = None  # Воркер может сначала загрузить фото без ML
    embeddings_data: dict[str, Any] | None = None


class FrameDetectionUpdate(BaseModel):
    detection_result: dict[str, Any]
    embeddings_data: dict[str, Any] | None = None


class FrameAnalysisResponse(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    project_id: uuid.UUID
    captured_at: datetime
    image_path: str
    image_url: str | None = None
    is_saved_for_report: bool
    detection_result: dict[str, Any] | None = None
    processed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class FrameEvidenceUpdate(BaseModel):
    is_saved_for_report: bool


class IntervalEquipmentSummary(BaseModel):
    required: list[dict[str, Any]] = []
    detected_active: list[dict[str, Any]] = []
    detected_idle: list[dict[str, Any]] = []
    unmonitored_zones: list[str] = []


class IntervalAnalyticsCreate(BaseModel):
    project_id: uuid.UUID
    schedule_id: uuid.UUID | None = None
    camera_id: uuid.UUID | None = None
    interval_start: datetime
    interval_end: datetime
    compliance_status: str  # "NORMAL", "WARNING", "VIOLATION"
    active_equipment_count: int = 0
    idle_equipment_count: int = 0
    required_equipment_count: int = 0
    equipment_summary: IntervalEquipmentSummary | dict[str, Any] = {}
    notes: str | None = None


class IntervalAnalyticsResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    schedule_id: uuid.UUID | None
    camera_id: uuid.UUID | None
    interval_start: datetime
    interval_end: datetime
    compliance_status: str
    active_equipment_count: int
    idle_equipment_count: int
    required_equipment_count: int
    equipment_summary: dict[str, Any] | list[dict[str, Any]]
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TriggerScenarioRequest(BaseModel):
    scenario_code: str = Field(
        ...,
        description="SCENARIO_NORMAL, SCENARIO_DEFICIT, SCENARIO_BLIND_SPOT, SCENARIO_AHEAD"
    )