"""Optional single-workload scheduler for scheduled backups."""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from scripts.backup import create_backup

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_weekly_backup() -> None:
    """Create a weekly backup without blocking the application event loop."""
    logger.info("Starting scheduled weekly backup...")
    try:
        filename = await asyncio.to_thread(create_backup, "weekly")
        logger.info("Weekly backup completed successfully: %s", filename)
    except Exception:
        logger.exception("Failed to create weekly backup")


async def run_monthly_backup() -> None:
    """Create a monthly backup without blocking the application event loop."""
    logger.info("Starting scheduled monthly backup...")
    try:
        filename = await asyncio.to_thread(create_backup, "monthly")
        logger.info("Monthly backup completed successfully: %s", filename)
    except Exception:
        logger.exception("Failed to create monthly backup")


def start_scheduler() -> None:
    """Start jobs once in a workload explicitly dedicated to scheduling."""
    if scheduler.running:
        return

    scheduler.add_job(
        run_weekly_backup,
        CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="weekly_backup",
        replace_existing=True,
    )
    scheduler.add_job(
        run_monthly_backup,
        CronTrigger(day="1", hour=4, minute=0),
        id="monthly_backup",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Backup scheduler started.")


def stop_scheduler() -> None:
    """Stop the local scheduler only when this process started it."""
    if not scheduler.running:
        return

    scheduler.shutdown()
    logger.info("Backup scheduler stopped.")
