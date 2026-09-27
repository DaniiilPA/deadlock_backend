import asyncio
from datetime import datetime, timezone
import logging
from typing import Any
import uuid
import numpy as np
from sqlalchemy import desc, select
from sqlalchemy.orm import selectinload

from app.core.utils import ensure_utc
from app.core.worker_config import get_worker_config
from app.db.models import (
    Alert,
    CameraFrameAnalysis,
    CameraIntervalAnalytics,
    Project,
    ProjectSchedule,
)
from app.db.session import AsyncSessionLocal
from app.ml.model import compute_cosine_similarity
from app.schemas import AlertTriggerRequest
from app.services.alert_service import AlertService
from app.services.schedule_service import ScheduleService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [ANALYTICS] %(message)s")
logger = logging.getLogger("analytics")


async def auto_resolve_alert(session, project_id: uuid.UUID, schedule_id: uuid.UUID, trigger_type: str) -> bool:
    stmt = (
        select(Alert)
        .where(
            Alert.project_id == project_id,
            Alert.schedule_id == schedule_id,
            Alert.trigger_type == trigger_type,
            Alert.status == "OPEN",
        )
    )
    open_alert = await session.scalar(stmt)
    if open_alert:
        open_alert.status = "RESOLVED"
        open_alert.resolved_at = datetime.now(timezone.utc)
        await session.flush()
        return True
    return False


async def run_analytics_task():
    logger.info("Analytics worker запущен")

    while True:
        cfg = get_worker_config()

        try:
            async with AsyncSessionLocal() as session:
                alert_service = AlertService(session)
                schedule_service = ScheduleService(session)
                now = datetime.now(timezone.utc)

                stmt = (
                    select(Project)
                    .where(Project.status == "ACTIVE")
                    .options(
                        selectinload(Project.schedules).selectinload(ProjectSchedule.equipment_requirements),
                        selectinload(Project.cameras),
                    )
                )
                projects = (await session.scalars(stmt)).all()

                for project in projects:
                    await schedule_service.sync_stage_statuses(project.id)

                    schedules_sorted = sorted(project.schedules, key=lambda x: x.sequence_order)
                    current_stage = next((s for s in schedules_sorted if s.status in ("IN_PROGRESS", "DELAYED")), None)
                    if not current_stage:
                        current_stage = next((s for s in schedules_sorted if s.status == "PLANNED"), None)
                    if not current_stage:
                        continue

                    needed_limit = cfg.window_frames_count * max(len(project.cameras), 1)
                    frames_stmt = (
                        select(CameraFrameAnalysis)
                        .where(
                            CameraFrameAnalysis.project_id == project.id,
                            CameraFrameAnalysis.processed_at.is_not(None),
                        )
                        .order_by(desc(CameraFrameAnalysis.captured_at))
                        .limit(needed_limit)
                    )
                    frames = list(reversed((await session.scalars(frames_stmt)).all()))
                    if len(frames) < 2:
                        continue

                    frames_by_cam: dict[uuid.UUID, list[CameraFrameAnalysis]] = {}
                    for f in frames:
                        frames_by_cam.setdefault(f.camera_id, []).append(f)

                    idle_by_class: dict[str, int] = {}
                    active_by_class: dict[str, int] = {}

                    for cam_id, cam_frames in frames_by_cam.items():
                        if len(cam_frames) < 2:
                            continue

                        first_dets = cam_frames[0].detection_result or []
                        last_dets = cam_frames[-1].detection_result or []
                        matched_last_indices = set()

                        for d1 in first_dets:
                            cls_name = d1.get("class", "unknown")
                            b1 = d1.get("bbox", [0, 0, 0, 0])
                            c1 = np.array([(b1[0] + b1[2]) / 2.0, (b1[1] + b1[3]) / 2.0])

                            best_idx = None
                            min_dist = float("inf")

                            for idx2, d2 in enumerate(last_dets):
                                if idx2 in matched_last_indices:
                                    continue
                                if d2.get("class") == cls_name:
                                    b2 = d2.get("bbox", [0, 0, 0, 0])
                                    c2 = np.array([(b2[0] + b2[2]) / 2.0, (b2[1] + b2[3]) / 2.0])
                                    dist = float(np.linalg.norm(c1 - c2))
                                    if dist < min_dist:
                                        min_dist = dist
                                        best_idx = idx2

                            if best_idx is not None:
                                matched_last_indices.add(best_idx)
                                if min_dist < cfg.idle_pixel_threshold:
                                    idle_by_class[cls_name] = idle_by_class.get(cls_name, 0) + 1
                                else:
                                    active_by_class[cls_name] = active_by_class.get(cls_name, 0) + 1
                            else:
                                active_by_class[cls_name] = active_by_class.get(cls_name, 0) + 1

                    total_idle = sum(idle_by_class.values())
                    total_active = sum(active_by_class.values())

                    latest_detections: list[dict[str, Any]] = []
                    latest_vectors: list[list[float]] = []

                    for cam_id, cam_frames in frames_by_cam.items():
                        last_frame = cam_frames[-1]
                        dets = last_frame.detection_result or []
                        embs = last_frame.embeddings_data or []
                        for idx, d in enumerate(dets):
                            vec = embs[idx].get("vector") if idx < len(embs) else []
                            det_dict = dict(d)
                            det_dict["_cam_id"] = str(cam_id)
                            latest_detections.append(det_dict)
                            latest_vectors.append(vec)

                    detected_unique_counts: dict[str, int] = {}
                    merged_indices = set()

                    for i in range(len(latest_detections)):
                        if i in merged_indices:
                            continue
                        cls_name = latest_detections[i].get("class", "unknown")
                        detected_unique_counts[cls_name] = detected_unique_counts.get(cls_name, 0) + 1
                        merged_indices.add(i)

                        for j in range(i + 1, len(latest_detections)):
                            if j in merged_indices:
                                continue
                            if (latest_detections[j].get("class") == cls_name and
                                    latest_detections[j].get("_cam_id") != latest_detections[i].get("_cam_id")):
                                sim = compute_cosine_similarity(latest_vectors[i], latest_vectors[j])
                                if sim >= cfg.reid_similarity_threshold:
                                    merged_indices.add(j)

                    total_unique = sum(detected_unique_counts.values())
                    req_map = {r.equipment_type: r.required_count for r in current_stage.equipment_requirements}
                    allowed_set = set(current_stage.allowed_equipment or [])
                    total_required = sum(req_map.values())

                    session.add(CameraIntervalAnalytics(
                        project_id=project.id,
                        schedule_id=current_stage.id,
                        camera_id=frames[-1].camera_id,
                        interval_start=frames[0].captured_at,
                        interval_end=frames[-1].captured_at,
                        active_equipment_count=total_active,
                        idle_equipment_count=total_idle,
                        required_equipment_count=total_required,
                        equipment_summary={
                            "required": req_map,
                            "allowed": list(allowed_set),
                            "detected_unique": detected_unique_counts,
                            "idle_breakdown": idle_by_class,
                        },
                        compliance_status="NORMAL" if total_idle == 0 else "WARNING",
                        notes=f"Окно {len(frames)} кадров. Уникальных: {total_unique}, простой: {total_idle}",
                    ))

                    need_recalc = False

                    if total_idle > 0:
                        await alert_service.trigger_alert(AlertTriggerRequest(
                            project_id=project.id,
                            schedule_id=current_stage.id,
                            severity="YELLOW",
                            trigger_type="EQUIPMENT_IDLE",
                            trigger_frame_id=frames[-1].id,
                            escalation_hours=24,
                            details={
                                "message": f"Простой техники ({total_idle} ед.)",
                                "risk_hint": current_stage.alerts_and_risks,
                            }
                        ))
                    else:
                        if await auto_resolve_alert(session, project.id, current_stage.id, "EQUIPMENT_IDLE"):
                            need_recalc = True

                    for req_type, req_cnt in req_map.items():
                        actual_cnt = detected_unique_counts.get(req_type, 0)
                        trigger_name = f"DEFICIT_{req_type.upper()}"
                        if actual_cnt < req_cnt:
                            sev = "RED" if current_stage.is_critical_path else "YELLOW"
                            await alert_service.trigger_alert(AlertTriggerRequest(
                                project_id=project.id,
                                schedule_id=current_stage.id,
                                severity=sev,
                                trigger_type=trigger_name,
                                trigger_frame_id=frames[-1].id,
                                escalation_hours=12,
                                details={
                                    "message": f"Нехватка: нужно {req_cnt} '{req_type}', обнаружено {actual_cnt}",
                                    "is_critical_path": current_stage.is_critical_path,
                                    "risk_hint": current_stage.alerts_and_risks,
                                }
                            ))
                        else:
                            if await auto_resolve_alert(session, project.id, current_stage.id, trigger_name):
                                need_recalc = True

                    for det_type in detected_unique_counts.keys():
                        trigger_name = f"MISMATCH_{det_type.upper()}"
                        if det_type not in req_map and det_type not in allowed_set:
                            await alert_service.trigger_alert(AlertTriggerRequest(
                                project_id=project.id,
                                schedule_id=current_stage.id,
                                severity="YELLOW",
                                trigger_type=trigger_name,
                                trigger_frame_id=frames[-1].id,
                                escalation_hours=8,
                                details={
                                    "message": f"Несогласованная техника: '{det_type}'",
                                    "risk_hint": current_stage.alerts_and_risks,
                                }
                            ))
                        else:
                            if await auto_resolve_alert(session, project.id, current_stage.id, trigger_name):
                                need_recalc = True

                    for req_type, req_cnt in req_map.items():
                        actual_cnt = detected_unique_counts.get(req_type, 0)
                        trigger_name = f"SURPLUS_{req_type.upper()}"
                        if actual_cnt > req_cnt + 2:
                            await alert_service.trigger_alert(AlertTriggerRequest(
                                project_id=project.id,
                                schedule_id=current_stage.id,
                                severity="YELLOW",
                                trigger_type=trigger_name,
                                details={"message": f"Избыток техники: {actual_cnt} при норме {req_cnt}"}
                            ))
                        else:
                            if await auto_resolve_alert(session, project.id, current_stage.id, trigger_name):
                                need_recalc = True

                    stage_start = ensure_utc(current_stage.base_start_date)
                    if current_stage.status == "PLANNED" and now < stage_start and total_active > 0:
                        await alert_service.trigger_alert(AlertTriggerRequest(
                            project_id=project.id,
                            schedule_id=current_stage.id,
                            severity="RED",
                            trigger_type="WORK_OFF_SCHEDULE",
                            details={"message": "Работы начаты до календарного старта этапа"}
                        ))

                    if need_recalc:
                        await alert_service._recalculate_project_alert_level(project)

                await session.commit()
                logger.info("Матрица окна обсчитана")
        except Exception as e:
            logger.error("Ошибка в analytics task: %s", e)

        await asyncio.sleep(cfg.analytics_interval_sec)


if __name__ == "__main__":
    asyncio.run(run_analytics_task())