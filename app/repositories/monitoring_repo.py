import uuid
from datetime import datetime
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Camera,
    CameraFrameAnalysis,
    CameraIntervalAnalytics,
    Project,
)


class MonitoringRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_project_by_id(self, project_id: uuid.UUID) -> Project | None:
        return await self._session.get(Project, project_id)

    async def get_camera_by_id(self, camera_id: uuid.UUID) -> Camera | None:
        return await self._session.get(Camera, camera_id)

    async def get_cameras_by_project_id(
        self, project_id: uuid.UUID, only_active: bool = False
    ) -> Sequence[Camera]:
        query = select(Camera).where(Camera.project_id == project_id)
        if only_active:
            query = query.where(Camera.is_active.is_(True))
        query = query.order_by(Camera.created_at.asc())
        return (await self._session.scalars(query)).all()

    async def delete_camera(self, camera: Camera) -> None:
        await self._session.delete(camera)

    async def get_frame_by_id(
        self, frame_id: uuid.UUID
    ) -> CameraFrameAnalysis | None:
        return await self._session.get(CameraFrameAnalysis, frame_id)

    async def list_frames(
        self,
        project_id: uuid.UUID,
        camera_id: uuid.UUID | None = None,
        from_datetime: datetime | None = None,
        to_datetime: datetime | None = None,
        is_saved_for_report: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[CameraFrameAnalysis]:
        query = (
            select(CameraFrameAnalysis)
            .where(CameraFrameAnalysis.project_id == project_id)
            .order_by(CameraFrameAnalysis.captured_at.desc())
        )
        if camera_id:
            query = query.where(CameraFrameAnalysis.camera_id == camera_id)
        if from_datetime:
            query = query.where(CameraFrameAnalysis.captured_at >= from_datetime)
        if to_datetime:
            query = query.where(CameraFrameAnalysis.captured_at <= to_datetime)
        if is_saved_for_report is not None:
            query = query.where(CameraFrameAnalysis.is_saved_for_report == is_saved_for_report)

        query = query.limit(limit).offset(offset)
        return (await self._session.scalars(query)).all()

    async def list_interval_analytics(
        self, project_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> Sequence[CameraIntervalAnalytics]:
        query = (
            select(CameraIntervalAnalytics)
            .where(CameraIntervalAnalytics.project_id == project_id)
            .order_by(CameraIntervalAnalytics.interval_end.desc())
            .limit(limit)
            .offset(offset)
        )
        return (await self._session.scalars(query)).all()

    def add(self, entity) -> None:
        self._session.add(entity)