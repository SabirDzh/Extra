from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from scripts.backup import create_backup

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

def run_weekly_backup():
    logger.info("Starting scheduled weekly backup...")
    try:
        filename = create_backup("weekly")
        logger.info(f"Weekly backup completed successfully: {filename}")
    except Exception as e:
        logger.error(f"Failed to create weekly backup: {e}")

def run_monthly_backup():
    logger.info("Starting scheduled monthly backup...")
    try:
        filename = create_backup("monthly")
        logger.info(f"Monthly backup completed successfully: {filename}")
    except Exception as e:
        logger.error(f"Failed to create monthly backup: {e}")

def start_scheduler():
    # Запускаем еженедельный бэкап каждое воскресенье в 03:00
    scheduler.add_job(
        run_weekly_backup,
        CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="weekly_backup",
        replace_existing=True
    )
    
    # Запускаем ежемесячный бэкап 1-го числа каждого месяца в 04:00
    scheduler.add_job(
        run_monthly_backup,
        CronTrigger(day="1", hour=4, minute=0),
        id="monthly_backup",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Backup scheduler started.")

def stop_scheduler():
    scheduler.shutdown()
    logger.info("Backup scheduler stopped.")
