import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .projects import Project, ProjectSchedule


class Camera(Base):
    __tablename__ = "cameras"

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
    stream_url: Mapped[str] = mapped_column(
        String(1024), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped["Project"] = relationship(back_populates="cameras")
    frame_analyses: Mapped[list["CameraFrameAnalysis"]] = relationship(
        back_populates="camera", cascade="all, delete-orphan"
    )
    interval_analytics: Mapped[list["CameraIntervalAnalytics"]] = relationship(
        back_populates="camera"
    )


class CameraFrameAnalysis(Base):
    __tablename__ = "camera_frame_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    image_path: Mapped[str] = mapped_column(
        String(1024), nullable=False
    )
    is_saved_for_report: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False, index=True
    )
    detection_result: Mapped[Any | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    embeddings_data: Mapped[Any | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True, default=None
    )

    camera: Mapped["Camera"] = relationship(back_populates="frame_analyses")
    project: Mapped["Project"] = relationship()


class CameraIntervalAnalytics(Base):
    __tablename__ = "camera_interval_analytics"

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
    camera_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        default=None,
    )
    interval_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    interval_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    equipment_summary: Mapped[list[dict[str, Any]] | dict[str, Any]] = mapped_column(
        JSONB, nullable=False
    )
    compliance_status: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped["Project"] = relationship()
    schedule: Mapped["ProjectSchedule | None"] = relationship()
    camera: Mapped["Camera | None"] = relationship(back_populates="interval_analytics")