import logging
import time

import aiohttp
from fastapi.encoders import jsonable_encoder

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
                log.info("Sent webhook, got response: %s", data)

except Exception as e:
    log.exception("Failed to send webhook for new user")
# TODO без этого тут выходит ошибка сериализации UUID, запрос обрабатывается скорее всего медленнее из-за того что я указал model_dump(mode="json"), надо исправить, как вариант, вообще убрать этот код, смысл его?
