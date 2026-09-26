from .common import (
    ErrorDetail,
    ErrorBody,
    ErrorResponse,
    MessageResponse,
)
from .users import (
    UserRegisterRequest,
    UserLoginRequest,
    UserRolesUpdateByEmailRequest,
    UserResponse,
    AuthResponse,
    TokenRefreshResponse,
)
from .dictionaries import (
    ProjectTypeResponse,
    ProjectTypeCreate,
    EquipmentTypeResponse,
    EquipmentTypeCreate,
    StageTemplateResponse,
    SystemSettingsResponse,
    SystemSettingsUpdate,
)
from .projects import (
    ProjectCreate,
    ProjectUpdate,
    ProjectAssignmentCreate,
    ProjectAssignmentResponse,
    ProjectDetailResponse,
    ProjectListItemResponse,
)
from .schedules import (
    ScheduleStatusEnum,
    ApplyTemplateRequest,
    ApplyTemplateResponse,
    StageEquipmentRequirementItem,
    StageEquipmentRequirementResponse,
    StageSyncItem,
    ScheduleBulkSyncRequest,
    ScheduleResponse,
    ScheduleCompleteEarlyRequest,
    CascadeShiftRequest,
    CascadeShiftResponse,
    CurrentStageRequirementsResponse,
)
from .monitoring import (
    CameraCreate,
    CameraUpdate,
    CameraResponse,
    FrameAnalysisCreate,
    FrameAnalysisResponse,
    FrameEvidenceUpdate,
    IntervalEquipmentSummary,
    IntervalAnalyticsCreate,
    IntervalAnalyticsResponse,
    TriggerScenarioRequest,
    FrameDetectionUpdate,
    FrameUploadResponse,
)
from .alerts import (
    AlertTriggerRequest,
    AlertResolveRequest,
    AlertResponse,
    AlertEscalationResponse,
)
from .special_statuses import (
    SpecialStatusCloseRequest,
    SpecialStatusResponse,
    OrangeStatusReportCreate,
    OrangeStatusReportResponse,
)
from .analytics import (
    LiveSummaryStage,
    LiveSummaryEquipment,
    LiveSummaryResponse,
    DepartmentOverviewResponse,
    AuditTrailResponse,
)

__all__ = [
    # common
    "ErrorDetail",
    "ErrorBody",
    "ErrorResponse",
    "MessageResponse",
    # users
    "UserRegisterRequest",
    "UserLoginRequest",
    "UserRolesUpdateByEmailRequest",
    "UserResponse",
    "AuthResponse",
    "TokenRefreshResponse",
    # dictionaries
    "ProjectTypeResponse",
    "ProjectTypeCreate",
    "EquipmentTypeResponse",
    "EquipmentTypeCreate",
    "StageTemplateResponse",
    "SystemSettingsResponse",
    "SystemSettingsUpdate",
    # projects
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectAssignmentCreate",
    "ProjectAssignmentResponse",
    "ProjectDetailResponse",
    "ProjectListItemResponse",
    # schedules
    "ScheduleStatusEnum",
    "ApplyTemplateRequest",
    "ApplyTemplateResponse",
    "StageEquipmentRequirementItem",
    "StageEquipmentRequirementResponse",
    "StageSyncItem",
    "ScheduleBulkSyncRequest",
    "ScheduleResponse",
    "ScheduleCompleteEarlyRequest",
    "CascadeShiftRequest",
    "CascadeShiftResponse",
    "CurrentStageRequirementsResponse",
    # monitoring
    "CameraCreate",
    "CameraUpdate",
    "CameraResponse",
    "FrameAnalysisCreate",
    "FrameAnalysisResponse",
    "FrameEvidenceUpdate",
    "IntervalEquipmentSummary",
    "IntervalAnalyticsCreate",
    "IntervalAnalyticsResponse",
    "TriggerScenarioRequest",
    "FrameDetectionUpdate",
    "FrameUploadResponse",
    # alerts
    "AlertTriggerRequest",
    "AlertResolveRequest",
    "AlertResponse",
    "AlertEscalationResponse",
    # special_statuses
    "SpecialStatusCloseRequest",
    "SpecialStatusResponse",
    "OrangeStatusReportCreate",
    "OrangeStatusReportResponse",
    # analytics
    "LiveSummaryStage",
    "LiveSummaryEquipment",
    "LiveSummaryResponse",
    "DepartmentOverviewResponse",
    "AuditTrailResponse",
]