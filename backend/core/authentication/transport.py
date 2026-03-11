from fastapi_users.authentication import (
    BearerTransport,
    CookieTransport,
)

from core.config import settings

bearer_transport = BearerTransport(
    tokenUrl=settings.api.bearer_token_url,
)
cookie_transport = CookieTransport(
    cookie_name=settings.cookie.name,
    cookie_max_age=settings.cookie.lifetime_seconds,
    cookie_secure=settings.cookie.secure,
    cookie_samesite=settings.cookie.samesite,
)
