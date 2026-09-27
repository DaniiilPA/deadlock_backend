import json
import logging
import os
from pydantic import BaseModel, Field

logger = logging.getLogger("worker_config")

CONFIG_FILE_PATH = "worker_config.json"


class WorkerRuntimeConfig(BaseModel):
    capture_interval_sec: int = Field(
        default=3,
        ge=1,
        le=300,
        description="Интервал создания/захвата кадров в секундах (Демо: 2-3с, Прод: 60с)",
    )
    analytics_interval_sec: int = Field(
        default=6,
        ge=2,
        le=600,
        description="Частота расчёта матрицы окна и поиска аномалий в секундах (Демо: 4-6с, Прод: 180с)",
    )
    window_frames_count: int = Field(
        default=10,
        ge=3,
        le=100,
        description="Высота матрицы анализа: количество последних кадров для оценки (Демо: 10, Прод: 30)",
    )
    idle_pixel_threshold: float = Field(
        default=15.0,
        ge=1.0,
        le=100.0,
        description="Зона нечувствительности трекера: смещение центра меньше этого числа пикселей считается простоем",
    )
    reid_similarity_threshold: float = Field(
        default=0.78,
        ge=0.5,
        le=0.99,
        description="Порог косинусного сходства для склейки одинаковых машин между разными камерами",
    )
    demo_scenario: str = Field(
        default="normal",
        description="Текущий режим симуляции: 'normal' (штатный), 'idle' (простой), 'deficit' (нехватка), 'mismatch' (чужая техника)",
    )


def get_worker_config() -> WorkerRuntimeConfig:
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return WorkerRuntimeConfig.model_validate_json(content)
        except Exception as e:
            logger.warning("Не удалось прочитать %s: %s. Используем дефолтные параметры.", CONFIG_FILE_PATH, e)

    return WorkerRuntimeConfig()


def save_worker_config(config: WorkerRuntimeConfig) -> None:
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(config.model_dump_json(indent=2))
        logger.info("Конфиг воркера успешно обновлен: %s", config.model_dump())
    except Exception as e:
        logger.error("Ошибка сохранения %s: %s", CONFIG_FILE_PATH, e)
        raise e