from fastapi_users.authentication import AuthenticationBackend

from core.authentication.transport import (

    cookie_transport,
)
from .strategy import get_database_strategy

authentication_backend = AuthenticationBackend(
    name="access-tokens-db",

    transport=cookie_transport,
    get_strategy=get_database_strategy,
)
