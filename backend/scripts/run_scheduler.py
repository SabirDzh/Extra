"""Run the backup scheduler in one explicitly dedicated process."""

import asyncio
import logging
import signal

from core.config import settings
from core.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


async def run_scheduler() -> None:
    """Keep one backup-scheduler process alive until it receives a stop signal."""
    if not settings.scheduler.enabled:
        logger.error("Scheduler is disabled; set APP_CONFIG__SCHEDULER__ENABLED=true.")
        return

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, stop_event.set)
        except NotImplementedError:
            # Signal handlers are unavailable on some non-Unix event loops.
            pass

    start_scheduler()
    try:
        await stop_event.wait()
    finally:
        stop_scheduler()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scheduler())
