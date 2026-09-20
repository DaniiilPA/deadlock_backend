import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .auth import User
    from .dictionaries import ProjectType, SystemSetting
    from .monitoring import Camera
    from .incidents import Alert, SpecialStatusWindow, AuditTrail


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    address: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'DRAFT'"), default="DRAFT"
    )
    schedule_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'DRAFT'"), default="DRAFT"
    )
    current_alert_level: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'GREEN'"), default="GREEN"
    )
    current_special_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'NONE'"), default="NONE"
    )
    yellow_alert_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    project_type: Mapped["ProjectType"] = relationship(back_populates="projects")
    creator: Mapped["User"] = relationship()
    system_setting: Mapped["SystemSetting | None"] = relationship(
        back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    assignments: Mapped[list["ProjectAssignment"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    schedules: Mapped[list["ProjectSchedule"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    cameras: Mapped[list["Camera"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    special_status_windows: Mapped[list["SpecialStatusWindow"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    audit_trails: Mapped[list["AuditTrail"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectAssignment(Base):
    __tablename__ = "project_assignments"

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
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_in_project: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped["Project"] = relationship(back_populates="assignments")
    user: Mapped["User"] = relationship()


class ProjectSchedule(Base):
    __tablename__ = "project_schedules"

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
    stage_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    substage_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    sequence_order: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    base_start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    base_end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    phantom_start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    phantom_end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    actual_start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    actual_end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'PLANNED'"), default="PLANNED"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped["Project"] = relationship(back_populates="schedules")
    equipment_requirements: Mapped[list["StageEquipmentRequirement"]] = relationship(
        back_populates="schedule", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(back_populates="schedule")


class StageEquipmentRequirement(Base):
    __tablename__ = "stage_equipment_requirements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    equipment_type: Mapped[str] = mapped_column(
        String(127), nullable=False, index=True
    )
    required_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1"), default=1
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    schedule: Mapped["ProjectSchedule"] = relationship(
        back_populates="equipment_requirements"
    )