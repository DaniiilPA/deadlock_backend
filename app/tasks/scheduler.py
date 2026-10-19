import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.session import AsyncSessionLocal
from app.services.alert_service import AlertService
from app.services.schedule_service import ScheduleService
from app.core.worker_config import get_worker_config
from app.services.monitoring_service import MonitoringService

logger = logging.getLogger("scheduler")
scheduler = AsyncIOScheduler()


async def check_escalations_job() -> None:
    async with AsyncSessionLocal() as session:
        try:
            alert_service = AlertService(session)
            escalated_ids = await alert_service.check_and_escalate_alerts()
            if escalated_ids:
                logger.info("Escalated %d alert(s) to RED: %s", len(escalated_ids), escalated_ids)

            expired_window_ids = await alert_service.check_and_expire_special_statuses()
            if expired_window_ids:
                logger.info("Auto-expired %d special status window(s): %s", len(expired_window_ids), expired_window_ids)
        except Exception as e:
            logger.error("Error during alert escalation check: %s", e)

async def sync_stages_job() -> None:
    async with AsyncSessionLocal() as session:
        try:
            schedule_service = ScheduleService(session)
            await schedule_service.sync_all_active_projects_stages()
        except Exception as e:
            logger.error("Error syncing project stages: %s", e)

async def cleanup_frames_job() -> None:
    async with AsyncSessionLocal() as session:
        try:
            retention = get_worker_config().frame_retention_minutes
            service = MonitoringService(session)
            stats = await service.cleanup_old_frames(retention)

            if stats["db_records_deleted"] > 0:
                logger.info(
                    "Cleanup кадров: удалено %d записей БД, %d файлов "
                    "(retention %d мин, отсутствовало %d файлов)",
                    stats["db_records_deleted"],
                    stats["files_deleted"],
                    stats["retention_minutes"],
                    stats["files_missing"],
                )
        except Exception as e:
            logger.error("Ошибка cleanup_frames_job: %s", e)


def start_scheduler() -> None:
    scheduler.add_job(
        check_escalations_job,
        "interval",
        seconds=60,
        id="check_escalations",
        replace_existing=True,
    )
    scheduler.add_job(
        sync_stages_job,
        "interval",
        minutes=5,
        id="sync_stages",
        replace_existing=True,
    )
    scheduler.add_job(
        cleanup_frames_job,
        "interval",
        minutes=1,
        id="cleanup_frames",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Background scheduler started (escalations: 60s, stages: 5m)")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background scheduler stopped")