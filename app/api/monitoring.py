import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_user,
    get_db,
    require_project_access,
    require_roles,
)
from app.db.models import User
from app.schemas import (
    CameraCreate,
    CameraResponse,
    CameraUpdate,
    FrameAnalysisCreate,
    FrameAnalysisResponse,
    FrameDetectionUpdate,
    FrameEvidenceUpdate,
    FrameUploadResponse,
    IntervalAnalyticsCreate,
    IntervalAnalyticsResponse,
    MessageResponse,
)
from app.services.monitoring_service import MonitoringService

router = APIRouter(tags=["Monitoring"])


def get_monitoring_service(session: AsyncSession = Depends(get_db)) -> MonitoringService:
    return MonitoringService(session)


@router.get(
    "/projects/{project_id}/cameras",
    response_model=list[CameraResponse],
    summary="Список камер объекта",
)
async def get_project_cameras(
    project_id: uuid.UUID,
    service: MonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(require_project_access()),
):
    return await service.list_cameras(project_id)


@router.post(
    "/projects/{project_id}/cameras",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Добавление камеры на стройплощадку",
)
async def create_camera(
    project_id: uuid.UUID,
    payload: CameraCreate,
    service: MonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(require_project_access("foreman", "engineer")),
):
    return await service.create_camera(project_id, payload)


@router.patch(
    "/cameras/{camera_id}",
    response_model=CameraResponse,
    summary="Редактирование/отключение камеры",
)
async def update_camera(
    camera_id: uuid.UUID,
    payload: CameraUpdate,
    service: MonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(require_roles("admin", "foreman", "engineer")),
):
    return await service.update_camera(camera_id, payload, current_user)


@router.delete(
    "/cameras/{camera_id}",
    response_model=MessageResponse,
    summary="Удаление камеры",
)
async def delete_camera(
    camera_id: uuid.UUID,
    service: MonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(require_roles("admin", "foreman")),
):
    await service.delete_camera(camera_id, current_user)
    return MessageResponse(message="Камера успешно удалена")


@router.post(
    "/cameras/{camera_id}/frames/upload",
    response_model=FrameUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Физическая загрузка файла снимка с камеры",
)
async def upload_frame(
    camera_id: uuid.UUID,
    file: UploadFile = File(...),
    service: MonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(get_current_user),
):
    file_path, image_url, filename = await service.save_uploaded_frame(camera_id, file)
    return FrameUploadResponse(
        image_path=file_path,
        image_url=image_url,
        filename=filename,
    )


@router.post(
    "/cameras/{camera_id}/frames",
    response_model=FrameAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Прием результатов детекции от ML-воркера",
)
async def record_frame(
    camera_id: uuid.UUID,
    payload: FrameAnalysisCreate,
    service: MonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(get_current_user),
):
    return await service.record_frame(camera_id, payload)


@router.patch(
    "/frames/{frame_id}/detection",
    response_model=FrameAnalysisResponse,
    summary="Сохранение детекции нейросети для ранее загруженного кадра",
)
async def update_frame_detection(
    frame_id: uuid.UUID,
    payload: FrameDetectionUpdate,
    service: MonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(get_current_user),
):
    frame = await service.update_frame_detection(frame_id, payload)
    return FrameAnalysisResponse(
        id=frame.id,
        camera_id=frame.camera_id,
        project_id=frame.project_id,
        captured_at=frame.captured_at,
        image_path=frame.image_path,
        image_url=f"/static/{os.path.basename(frame.image_path)}" if frame.image_path else None,
        is_saved_for_report=frame.is_saved_for_report,
        detection_result=frame.detection_result,
        processed_at=frame.processed_at,
    )


@router.get(
    "/projects/{project_id}/frames",
    response_model=list[FrameAnalysisResponse],
    summary="Галерея снимков с рамочками техники (для фронтенда)",
)
async def list_project_frames(
    project_id: uuid.UUID,
    camera_id: uuid.UUID | None = None,
    from_datetime: datetime | None = None,
    to_datetime: datetime | None = None,
    is_saved_for_report: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    service: MonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(require_project_access()),
):
    return await service.list_frames(
        project_id=project_id,
        camera_id=camera_id,
        from_datetime=from_datetime,
        to_datetime=to_datetime,
        is_saved_for_report=is_saved_for_report,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/frames/{frame_id}/evidence",
    response_model=MessageResponse,
    summary="Закрепить кадр как улику нарушения (Инженер)",
)
async def set_frame_evidence(
    frame_id: uuid.UUID,
    payload: FrameEvidenceUpdate,
    service: MonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(require_roles("engineer")),
):
    await service.set_frame_evidence(frame_id, payload.is_saved_for_report)
    return MessageResponse(message="Статус улики успешно обновлен")


@router.post(
    "/monitoring/interval-analytics",
    response_model=IntervalAnalyticsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Прием 20-30 минутной интервальной сводки от воркера",
)
async def record_interval_analytics(
    payload: IntervalAnalyticsCreate,
    service: MonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(get_current_user),
):
    return await service.record_interval_analytics(payload)


@router.get(
    "/projects/{project_id}/interval-analytics",
    response_model=list[IntervalAnalyticsResponse],
    summary="История интервальной активности объекта для графиков",
)
async def list_interval_analytics(
    project_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    service: MonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(require_project_access()),
):
    return await service.list_interval_analytics(project_id, limit, offset)