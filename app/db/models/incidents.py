import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .auth import User
    from .monitoring import CameraFrameAnalysis
    from .projects import Project, ProjectSchedule


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        default=None,
    )
    severity: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True
    )
    trigger_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, server_default=text("'OPEN'"), default="OPEN"
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    escalate_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
    )
    yellow_escalated_to_red_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    trigger_frame_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("camera_frame_analyses.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        index=True,
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, default=None
    )

    project: Mapped["Project"] = relationship(back_populates="alerts")
    schedule: Mapped["ProjectSchedule | None"] = relationship(back_populates="alerts")
    trigger_frame: Mapped["CameraFrameAnalysis | None"] = relationship()
    resolution: Mapped["AlertResolution | None"] = relationship(
        back_populates="alert", uselist=False, cascade="all, delete-orphan"
    )
    special_status_windows: Mapped[list["SpecialStatusWindow"]] = relationship(
        back_populates="alert"
    )

    __table_args__ = (
        Index(
            "uq_open_alert_per_stage_trigger",
            "project_id",
            # Защита от NULL != NULL в PostgreSQL:
            text("COALESCE(schedule_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "trigger_type",
            unique=True,
            postgresql_where=(text("status = 'OPEN'")),
        ),
    )


class AlertResolution(Base):
    __tablename__ = "alert_resolutions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    engineer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action_taken: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    engineer_comment: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    evidence_frame_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True, default=None
    )
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    alert: Mapped["Alert"] = relationship(back_populates="resolution")
    engineer: Mapped["User"] = relationship()


class SpecialStatusWindow(Base):
    __tablename__ = "special_status_windows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    target_deadline: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actual_end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    reason_comment: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    close_comment: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )

    project: Mapped["Project"] = relationship(back_populates="special_status_windows")
    alert: Mapped["Alert"] = relationship(back_populates="special_status_windows")
    created_by_user: Mapped["User"] = relationship()
    orange_status_report: Mapped["OrangeStatusReport | None"] = relationship(
        back_populates="special_status_window", uselist=False, cascade="all, delete-orphan"
    )


class OrangeStatusReport(Base):
    __tablename__ = "orange_status_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    special_status_window_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("special_status_windows.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    is_plan_caught_up: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    time_lost_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    responsible_party: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    summary_meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    special_status_window: Mapped["SpecialStatusWindow"] = relationship(
        back_populates="orange_status_report"
    )


class AuditTrail(Base):
    __tablename__ = "audit_trail"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        default=None,
    )
    action_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    old_values: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    new_values: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    project: Mapped["Project"] = relationship(back_populates="audit_trails")
    user: Mapped["User | None"] = relationship()