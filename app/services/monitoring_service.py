import os
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundException, ProjectNotFoundException
from app.db.models import Camera, CameraFrameAnalysis, CameraIntervalAnalytics
from app.repositories.monitoring_repo import MonitoringRepository
from app.schemas.monitoring import (
    CameraCreate,
    CameraUpdate,
    FrameAnalysisCreate,
    FrameAnalysisResponse,
    IntervalAnalyticsCreate,
    FrameDetectionUpdate,
)


class MonitoringService:
    def __init__(
        self,
        session: AsyncSession,
        monitoring_repo: MonitoringRepository | None = None,
    ) -> None:
        self._session = session
        self._repo = monitoring_repo or MonitoringRepository(session)

    # Управление точками обзора (Камерами)

    async def create_camera(self, project_id: uuid.UUID, data: CameraCreate) -> Camera:
        project = await self._repo.get_project_by_id(project_id)
        if not project:
            raise ProjectNotFoundException(project_id)

        camera = Camera(
            project_id=project_id,
            stream_url=data.stream_url,
            is_active=True,
        )
        self._repo.add(camera)
        await self._session.commit()
        return camera

    async def list_cameras(self, project_id: uuid.UUID) -> list[Camera]:
        await self._ensure_project_exists(project_id)
        return list(await self._repo.get_cameras_by_project_id(project_id))

    async def update_camera(self, camera_id: uuid.UUID, data: CameraUpdate) -> Camera:
        camera = await self._repo.get_camera_by_id(camera_id)
        if not camera:
            raise EntityNotFoundException(f"Камера {camera_id} не найдена")

        if data.stream_url is not None:
            camera.stream_url = data.stream_url
        if data.is_active is not None:
            camera.is_active = data.is_active

        await self._session.commit()
        return camera

    async def delete_camera(self, camera_id: uuid.UUID) -> None:
        camera = await self._repo.get_camera_by_id(camera_id)
        if not camera:
            raise EntityNotFoundException(f"Камера {camera_id} не найдена")

        await self._repo.delete_camera(camera)
        await self._session.commit()

    # Приемка кадров от воркера и выдача фронту

    async def record_frame(
        self, camera_id: uuid.UUID, data: FrameAnalysisCreate
    ) -> CameraFrameAnalysis:
        """Воркер присылает результат детекции по кадру"""
        camera = await self._repo.get_camera_by_id(camera_id)
        if not camera:
            raise EntityNotFoundException(f"Камера {camera_id} не найдена")

        frame = CameraFrameAnalysis(
            camera_id=camera.id,
            project_id=camera.project_id,
            captured_at=data.captured_at,
            image_path=data.image_path,
            detection_result=data.detection_result,
            embeddings_data=data.embeddings_data,
            processed_at=datetime.now(timezone.utc),
            is_saved_for_report=False,
        )
        self._repo.add(frame)
        await self._session.commit()
        return frame

    async def list_frames(
        self,
        project_id: uuid.UUID,
        camera_id: uuid.UUID | None = None,
        from_datetime: datetime | None = None,
        to_datetime: datetime | None = None,
        is_saved_for_report: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FrameAnalysisResponse]:
        """Фронтенд запрашивает галерею кадров с рамочками техники"""
        await self._ensure_project_exists(project_id)
        frames = await self._repo.list_frames(
            project_id=project_id,
            camera_id=camera_id,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
            is_saved_for_report=is_saved_for_report,
            limit=limit,
            offset=offset,
        )

        result: list[FrameAnalysisResponse] = []
        for f in frames:
            file_name = os.path.basename(f.image_path)
            image_url = f"/static/{file_name}" if f.image_path else None

            result.append(
                FrameAnalysisResponse(
                    id=f.id,
                    camera_id=f.camera_id,
                    project_id=f.project_id,
                    captured_at=f.captured_at,
                    image_path=f.image_path,
                    image_url=image_url,
                    is_saved_for_report=f.is_saved_for_report,
                    detection_result=f.detection_result,
                    processed_at=f.processed_at,
                )
            )
        return result

    async def set_frame_evidence(
        self, frame_id: uuid.UUID, is_saved_for_report: bool
    ) -> CameraFrameAnalysis:
        """Инженер помечает кадр как доказательство нарушения"""
        frame = await self._repo.get_frame_by_id(frame_id)
        if not frame:
            raise EntityNotFoundException("Кадр не найден")

        frame.is_saved_for_report = is_saved_for_report
        await self._session.commit()
        return frame

    # Приемка и выдача интервальных сводок от воркера

    async def record_interval_analytics(
        self, data: IntervalAnalyticsCreate
    ) -> CameraIntervalAnalytics:
        """Воркер присылает рассчитанную им сводку за 20-30 минут"""
        await self._ensure_project_exists(data.project_id)

        summary = (
            data.equipment_summary.model_dump()
            if hasattr(data.equipment_summary, "model_dump")
            else data.equipment_summary
        )

        analytics = CameraIntervalAnalytics(
            project_id=data.project_id,
            schedule_id=data.schedule_id,
            camera_id=data.camera_id,
            interval_start=data.interval_start,
            interval_end=data.interval_end,
            compliance_status=data.compliance_status,
            equipment_summary=summary,
            notes=data.notes,
        )
        self._repo.add(analytics)
        await self._session.commit()
        return analytics

    async def list_interval_analytics(
        self, project_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[CameraIntervalAnalytics]:
        """Фронтенд запрашивает историю интервалов для графика активности"""
        await self._ensure_project_exists(project_id)
        return list(await self._repo.list_interval_analytics(project_id, limit, offset))

    async def _ensure_project_exists(self, project_id: uuid.UUID) -> None:
        project = await self._repo.get_project_by_id(project_id)
        if not project:
            raise ProjectNotFoundException(project_id)
        
    async def update_frame_detection(
        self, frame_id: uuid.UUID, data: FrameDetectionUpdate
    ) -> CameraFrameAnalysis:
        frame = await self._repo.get_frame_by_id(frame_id)
        if not frame:
            raise EntityNotFoundException(f"Кадр {frame_id} не найден")

        frame.detection_result = data.detection_result
        frame.embeddings_data = data.embeddings_data
        frame.processed_at = datetime.now(timezone.utc)

        await self._session.commit()
        return frame