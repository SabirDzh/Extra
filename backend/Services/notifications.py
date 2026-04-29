import logging
import os
import time

import aiohttp
from core.models import User
from core.schemas.user import UserRead, UserRegisteredNotification

log = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://httpbin.org/post")


async def send_new_user_notification(user: User) -> None:
    if not WEBHOOK_URL:
        log.debug("WEBHOOK_URL is empty, skipping new user notification webhook")
        return

    try:
        wh_data = UserRegisteredNotification(
            user=UserRead.model_validate(user),
            ts=int(time.time()),
        ).model_dump(mode="json")

        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(WEBHOOK_URL, json=wh_data) as response:
                response.raise_for_status()
                await response.json()

    except Exception:
        # Webhook must be best-effort and should never break user registration/tests.
        log.exception("Failed to send webhook for new user")



