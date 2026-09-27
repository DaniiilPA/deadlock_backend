import uuid
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field


class ScheduleStatusEnum(StrEnum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DELAYED = "DELAYED"


class ApplyTemplateRequest(BaseModel):
    start_date: datetime


class ApplyTemplateResponse(BaseModel):
    created_stages_count: int
    status: str
    message: str


class StageEquipmentRequirementItem(BaseModel):
    equipment_type: str
    required_count: int = Field(1, ge=1)


class StageEquipmentRequirementResponse(BaseModel):
    id: uuid.UUID
    schedule_id: uuid.UUID
    equipment_type: str
    required_count: int

    model_config = ConfigDict(from_attributes=True)


class StageSyncItem(BaseModel):
    id: uuid.UUID | None = None
    stage_name: str
    substage_name: str
    sequence_order: int
    base_start_date: datetime
    base_end_date: datetime
    equipment_requirements: list[StageEquipmentRequirementItem] = []


class ScheduleBulkSyncRequest(BaseModel):
    stages: list[StageSyncItem]


class ScheduleResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    stage_name: str
    substage_name: str
    sequence_order: int
    base_start_date: datetime
    base_end_date: datetime
    phantom_start_date: datetime | None = None
    phantom_end_date: datetime | None = None
    actual_start_date: datetime | None = None
    actual_end_date: datetime | None = None
    status: ScheduleStatusEnum
    is_critical_path: bool = False
    allowed_equipment: list[str] = []
    alerts_and_risks: str | None = None
    equipment_requirements: list[StageEquipmentRequirementResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ScheduleCompleteEarlyRequest(BaseModel):
    actual_end_date: datetime
    foreman_comment: str


class CascadeShiftRequest(BaseModel):
    from_schedule_id: uuid.UUID
    shift_days: int  # < 0 опережение (влево), > 0 задержка (вправо)
    target_timeline: str = "PHANTOM"  # "PHANTOM" или "BASE"
    reason_comment: str
    document_reference: str | None = None
    close_special_status: bool = False


class CascadeShiftResponse(BaseModel):
    shifted_stages_count: int
    old_estimated_completion: datetime
    new_estimated_completion: datetime
    audit_trail_id: uuid.UUID
    
class CurrentStageRequirementsResponse(BaseModel):
    schedule_id: uuid.UUID
    project_id: uuid.UUID
    stage_name: str
    substage_name: str
    sequence_order: int
    status: str
    base_start_date: datetime
    base_end_date: datetime
    required_equipment: list[StageEquipmentRequirementResponse] = []

    model_config = ConfigDict(from_attributes=True)    