import asyncio
from datetime import datetime, timezone
import logging
import os
import shutil
import uuid
import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.worker_config import get_worker_config
from app.db.models import Camera, CameraFrameAnalysis, Project
from app.db.session import AsyncSessionLocal
from app.ml.model import ModelPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [VISION] %(message)s")
logger = logging.getLogger("vision")

ml_pipeline = ModelPipeline()


async def fetch_camera_frame(client: httpx.AsyncClient, stream_url: str, target_path: str) -> bool:
    if stream_url.startswith("http://") or stream_url.startswith("https://"):
        try:
            resp = await client.get(stream_url, timeout=4.0)
            if resp.status_code == 200 and resp.content:
                with open(target_path, "wb") as f:
                    f.write(resp.content)
                return True
            else:
                logger.warning("Камера %s вернула статус HTTP %d", stream_url, resp.status_code)
                return False
        except Exception as e:
            logger.warning("Сбой связи с камерой %s: %s", stream_url, e)
            return False

    if os.path.exists(stream_url) and os.path.isfile(stream_url):
        try:
            shutil.copyfile(stream_url, target_path)
            return True
        except Exception as e:
            logger.warning("Ошибка копирования локального файла %s: %s", stream_url, e)
            return False

    logger.warning("Камера недоступна (неверный путь или URL): %s", stream_url)
    return False


async def run_vision_task():
    logger.info("Vision worker запущен")
    os.makedirs("storage", exist_ok=True)

    async with httpx.AsyncClient() as http_client:
        while True:
            cfg = get_worker_config()

            try:
                async with AsyncSessionLocal() as session:
                    stmt = (
                        select(Project)
                        .where(Project.status == "ACTIVE")
                        .options(selectinload(Project.cameras))
                    )
                    projects = (await session.scalars(stmt)).all()
                    now = datetime.now(timezone.utc)

                    for project in projects:
                        for camera in project.cameras:
                            if not camera.is_active:
                                continue

                            filename = f"cam_{camera.id}_{int(now.timestamp())}.jpg"
                            target_path = os.path.join("storage", filename)

                            success = await fetch_camera_frame(http_client, camera.stream_url, target_path)
                            if not success:
                                continue

                            detections, embeddings = await asyncio.to_thread(
                                ml_pipeline.process_frame, target_path
                            )

                            session.add(CameraFrameAnalysis(
                                camera_id=camera.id,
                                project_id=project.id,
                                captured_at=now,
                                image_path=target_path,
                                detection_result=detections,
                                embeddings_data=embeddings,
                                processed_at=now,
                                is_saved_for_report=False,
                            ))

                    await session.commit()
            except Exception as e:
                logger.error("Ошибка в vision task: %s", e)

            await asyncio.sleep(cfg.capture_interval_sec)


if __name__ == "__main__":
    asyncio.run(run_vision_task())