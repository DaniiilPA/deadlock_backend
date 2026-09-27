import asyncio
from datetime import datetime, timezone
import logging
import os
import shutil
import uuid
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.worker_config import get_worker_config
from app.db.models import Camera, CameraFrameAnalysis, Project
from app.db.session import AsyncSessionLocal
from app.ml.model import ModelPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [VISION] %(message)s",
)
logger = logging.getLogger("vision")

ml_pipeline = ModelPipeline()


def get_simulated_frame(target_path: str, camera_id: uuid.UUID, scenario: str) -> None:
    """
    Генерирует или подбирает картинку под текущий демо-сценарий:
    - Если в папке demo_data есть картинка под сценарий - берет её
    - Если в корне есть test.jpg - использует его
    - Иначе генерирует легковесный синтетический кадр
    """
    scenario_dir = os.path.join("demo_data", scenario)
    cam_scenario_img = os.path.join(scenario_dir, f"cam_{camera_id}.jpg")

    if os.path.exists(cam_scenario_img):
        shutil.copyfile(cam_scenario_img, target_path)
        return

    # Проверяем файлы test.jpg
    sample_file = "test.jpg" if os.path.exists("test.jpg") else (
        "test.jpeg" if os.path.exists("test.jpeg") else None
    )

    if sample_file:
        shutil.copyfile(sample_file, target_path)
    else:
        # Резервный синтетический кадр 640x480
        color = (90, 95, 100) if scenario != "deficit" else (60, 60, 60)
        img = Image.new("RGB", (640, 480), color=color)
        img.save(target_path)


async def run_vision_task():
    logger.info("Запущен сервис компьютерного зрения (Vision Worker)")
    os.makedirs("storage", exist_ok=True)

    cleanup_counter = 0

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

                        get_simulated_frame(target_path, camera.id, cfg.demo_scenario)

                        detections, embeddings = await asyncio.to_thread(
                            ml_pipeline.process_frame, target_path
                        )

                        # Сохраняем в базу готовый результат
                        frame_record = CameraFrameAnalysis(
                            camera_id=camera.id,
                            project_id=project.id,
                            captured_at=now,
                            image_path=target_path,
                            detection_result=detections,
                            embeddings_data=embeddings,
                            processed_at=now,
                            is_saved_for_report=False,
                        )
                        session.add(frame_record)

                await session.commit()

            # Периодическая очистка старых кадров с диска (каждые 40 тактов)
            cleanup_counter += 1
            if cleanup_counter >= 40:
                cleanup_counter = 0
                now_ts = datetime.now(timezone.utc).timestamp()
                # Удаляем временные снимки старше 15 минут, если они не помечены как улики
                for fname in os.listdir("storage"):
                    fpath = os.path.join("storage", fname)
                    if os.path.isfile(fpath) and (now_ts - os.path.getmtime(fpath)) > 900:
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass

        except Exception as e:
            logger.error("Ошибка при обработке кадров: %s", e)

        await asyncio.sleep(cfg.capture_interval_sec)


if __name__ == "__main__":
    asyncio.run(run_vision_task())