import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .projects import Project


class ProjectType(Base):
    __tablename__ = "project_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    code: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(127), nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), default=True
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

    stage_templates: Mapped[list["StageTemplate"]] = relationship(
        back_populates="project_type", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(back_populates="project_type")


class EquipmentType(Base):
    __tablename__ = "equipment_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    code: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(127), nullable=False
    )
    ml_class_names: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class StageTemplate(Base):
    __tablename__ = "stage_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_types.id", ondelete="CASCADE"),
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
    default_duration_days: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    default_equipment: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False
    )
    is_critical_path: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    allowed_equipment: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("ARRAY[]::varchar[]"), default=list
    )
    alerts_and_risks: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
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

    project_type: Mapped["ProjectType"] = relationship(
        back_populates="stage_templates"
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        index=True,
        default=None,
    )
    yellow_to_red_timeout_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("48"), default=48
    )
    idle_threshold_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("30"), default=30
    )
    frame_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("7"), default=7
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

    project: Mapped["Project | None"] = relationship(back_populates="system_setting")