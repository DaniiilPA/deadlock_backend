import json
import logging
import os
from pydantic import BaseModel, Field

logger = logging.getLogger("worker_config")
CONFIG_FILE_PATH = "worker_config.json"


class WorkerRuntimeConfig(BaseModel):
    capture_interval_sec: int = Field(default=3, ge=1, le=300)
    analytics_interval_sec: int = Field(default=6, ge=2, le=600)
    window_frames_count: int = Field(default=10, ge=3, le=100)
    idle_pixel_threshold: float = Field(default=15.0, ge=1.0, le=100.0)
    reid_similarity_threshold: float = Field(default=0.78, ge=0.5, le=0.99)


def get_worker_config() -> WorkerRuntimeConfig:
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return WorkerRuntimeConfig.model_validate_json(content)
        except Exception as e:
            logger.warning("Ошибка чтения %s: %s", CONFIG_FILE_PATH, e)
    return WorkerRuntimeConfig()


def save_worker_config(config: WorkerRuntimeConfig) -> None:
    with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(config.model_dump_json(indent=2))