import asyncio
import logging

from app.tasks.analytics import run_analytics_task
from app.tasks.vision import run_vision_task

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [PIPELINE] %(message)s")
logger = logging.getLogger("pipeline")


async def main():
    logger.info("Запуск воркера видеоаналитики")
    await asyncio.gather(
        run_vision_task(),
        run_analytics_task(),
    )


if __name__ == "__main__":
    asyncio.run(main())