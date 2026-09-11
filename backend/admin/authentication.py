"""Authentication for the SQLAdmin interface.

The API and SQLAdmin share the same database-backed access token.  This keeps
the administrative interface behind the application's existing login flow
instead of exposing a separate password form.
"""

from datetime import datetime, timedelta, timezone
from core.config import settings
from core.models import AccessToken, User, db_helper
from Domain.Enums.user_role import UserRole
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

class AdminAuthenticationBackend(AuthenticationBackend):
    """Authorize SQLAdmin requests with an active administrator API session."""

    async def login(self, request: Request) -> bool:
        """Disable SQLAdmin's separate login form.

        Users must authenticate through the API login endpoint so a single
        token lifecycle is used across the application.

        Args:
            request: Incoming SQLAdmin login request.

        Returns:
            Always ``False`` because this backend does not handle credentials.
        """
        return False

    async def logout(self, request: Request) -> bool:
        """Clear the SQLAdmin session wrapper without touching the API token.

        Args:
            request: Incoming SQLAdmin logout request.

        Returns:
            ``True`` after the temporary SQLAdmin session is cleared.
        """
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> Response | bool:
        """Allow only non-expired access tokens owned by active administrators.

        Args:
            request: Request to an SQLAdmin route.

        Returns:
            ``True`` for an authorized administrator, otherwise a 401 response.
        """
        token = request.cookies.get(settings.cookie.name)
        if not token:
            return PlainTextResponse("Admin authentication required", status_code=401)

        token_created_after = datetime.now(timezone.utc) - timedelta(
            seconds=settings.access_token.lifetime_seconds,
        )
        statement = (
            select(User.id)
            .join(AccessToken, AccessToken.user_id == User.id)
            .where(
                AccessToken.token == token,
                AccessToken.created_at >= token_created_after,
                User.is_active.is_(True),
                User.role == UserRole.admin,
            )
        )

        async with db_helper.session_factory() as session:
            user_id = await session.scalar(statement)

        return user_id is not None


admin_authentication_backend = AdminAuthenticationBackend(
    secret_key=(
        settings.security.admin_session_secret or settings.access_token.verification_token_secret
    ),
)
