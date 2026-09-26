import os
import anyio
import shutil
import uuid
from datetime import datetime, timezone
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainException, EntityNotFoundException, ProjectNotFoundException
from app.db.models import Camera, CameraFrameAnalysis, CameraIntervalAnalytics, User
from app.repositories.monitoring_repo import MonitoringRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.monitoring import (
    CameraCreate,
    CameraUpdate,
    FrameAnalysisCreate,
    FrameDetectionUpdate,
    IntervalAnalyticsCreate,
)


class MonitoringService:
    def __init__(
        self,
        session: AsyncSession,
        monitoring_repo: MonitoringRepository | None = None,
        project_repo: ProjectRepository | None = None,
    ) -> None:
        self._session = session
        self._repo = monitoring_repo or MonitoringRepository(session)
        self._project_repo = project_repo or ProjectRepository(session)

    async def _check_camera_permission(self, camera: Camera, user: User) -> None:
        if "admin" in user.roles:
            return
        assignment = await self._project_repo.get_assignment(camera.project_id, user.id)
        if not assignment or assignment.role_in_project not in ("foreman", "engineer"):
            raise DomainException(
                message="Недостаточно прав. Вы должны быть назначены прорабом или инженером на данный объект строительства",
                status_code=403,
            )

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

    async def update_camera(
        self, camera_id: uuid.UUID, data: CameraUpdate, current_user: User
    ) -> Camera:
        camera = await self._repo.get_camera_by_id(camera_id)
        if not camera:
            raise EntityNotFoundException(f"Камера {camera_id} не найдена")

        await self._check_camera_permission(camera, current_user)

        if data.stream_url is not None:
            camera.stream_url = data.stream_url
        if data.is_active is not None:
            camera.is_active = data.is_active

        await self._session.commit()
        return camera

    async def delete_camera(self, camera_id: uuid.UUID, current_user: User) -> None:
        camera = await self._repo.get_camera_by_id(camera_id)
        if not camera:
            raise EntityNotFoundException(f"Камера {camera_id} не найдена")

        await self._check_camera_permission(camera, current_user)

        await self._repo.delete_camera(camera)
        await self._session.commit()

    async def save_uploaded_frame(
        self, camera_id: uuid.UUID, file: UploadFile, current_user: User
    ) -> tuple[str, str, str]:
        camera = await self._repo.get_camera_by_id(camera_id)
        if not camera:
            raise EntityNotFoundException(f"Камера {camera_id} не найдена")

        await self._check_camera_permission(camera, current_user)

        os.makedirs("storage", exist_ok=True)
        ext = os.path.splitext(file.filename or "")[1].lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            raise DomainException("Недопустимый формат файла. Разрешены: jpg, jpeg, png, webp")

        filename = f"{uuid.uuid4()}{ext}"
        file_path = os.path.join("storage", filename)

        max_size = 15 * 1024 * 1024
        chunk_size = 1024 * 1024

        def _write_to_disk():
            total_bytes = 0
            try:
                with open(file_path, "wb") as buffer:
                    while chunk := file.file.read(chunk_size):
                        total_bytes += len(chunk)
                        if total_bytes > max_size:
                            raise DomainException(
                                message="Размер загружаемого файла превышает допустимый лимит 15 МБ",
                                status_code=413,
                            )
                        buffer.write(chunk)
            except Exception:
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise

        await anyio.to_thread.run_sync(_write_to_disk)

        image_url = f"/static/{filename}"
        return file_path, image_url, filename
    
    async def record_frame(
        self, camera_id: uuid.UUID, data: FrameAnalysisCreate
    ) -> CameraFrameAnalysis:
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
    ) -> list[CameraFrameAnalysis]:
        await self._ensure_project_exists(project_id)
        return list(
            await self._repo.list_frames(
                project_id=project_id,
                camera_id=camera_id,
                from_datetime=from_datetime,
                to_datetime=to_datetime,
                is_saved_for_report=is_saved_for_report,
                limit=limit,
                offset=offset,
            )
        )

    async def set_frame_evidence(
        self, frame_id: uuid.UUID, is_saved_for_report: bool, current_user: User
    ) -> CameraFrameAnalysis:
        frame = await self._repo.get_frame_by_id(frame_id)
        if not frame:
            raise EntityNotFoundException("Кадр не найден")

        if "admin" not in current_user.roles:
            assignment = await self._project_repo.get_assignment(frame.project_id, current_user.id)
            if not assignment or assignment.role_in_project != "engineer":
                raise DomainException(
                    message="Недостаточно прав. Вы не назначены инженером на данный объект строительства",
                    status_code=403,
                )

        frame.is_saved_for_report = is_saved_for_report
        await self._session.commit()
        return frame

    async def record_interval_analytics(
        self, data: IntervalAnalyticsCreate
    ) -> CameraIntervalAnalytics:
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
            active_equipment_count=data.active_equipment_count,
            idle_equipment_count=data.idle_equipment_count,
            required_equipment_count=data.required_equipment_count,
            equipment_summary=summary,
            notes=data.notes,
        )
        self._repo.add(analytics)
        await self._session.commit()
        return analytics

    async def list_interval_analytics(
        self, project_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[CameraIntervalAnalytics]:
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