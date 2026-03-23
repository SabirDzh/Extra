import logging
import time

import aiohttp
from core.models import User
from core.schemas.user import UserRead, UserRegisteredNotification

log = logging.getLogger(__name__)

WEBHOOK_URL = "https://httpbin.org/post"


try:

    async def send_new_user_notification(user: User) -> None:
        wh_data = UserRegisteredNotification(
            user=UserRead.model_validate(user),
            ts=int(time.time()),
        ).model_dump(mode="json")
        # log.info("Notify user created with data: %s", wh_data)
        async with aiohttp.ClientSession() as session:
            async with session.post(WEBHOOK_URL, json=wh_data) as response:
                data = await response.json()
                # log.info("Sent webhook, got response: %s", data)

except Exception as e:
    log.exception("Failed to send webhook for new user")

# TODO without this there is a UUID serialization error.
# The request is likely slower due to model_dump(mode="json"). Revisit this implementation
# or consider removing it if it has no value.
