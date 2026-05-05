from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from fastapi_users import exceptions
from fastapi_users.manager import BaseUserManager
from api.dependencies.authentication import get_user_manager
from core.config import settings
from jinja_templates import templates

router = APIRouter(
    prefix="/verify-email",
)


@router.get(
    "/",
    include_in_schema=False,
    name="verify_email",
)
async def verify_email(
    request: Request,
    token: str | None = Query(None),
    user_manager: BaseUserManager = Depends(get_user_manager),
):
    if token:
        try:
            # Verify on backend first, then redirect with result only (no token leak).
            await user_manager.verify(token, request)
            params = {"verified": "1"}
        except exceptions.UserAlreadyVerified:
            params = {"verified": "1", "already": "1"}
        except (exceptions.InvalidVerifyToken, exceptions.UserNotExists):
            params = {"verified": "0", "reason": "bad_token"}
        except exceptions.UserInactive:
            params = {"verified": "0", "reason": "inactive"}
        except Exception:
            params = {"verified": "0", "reason": "server_error"}

        redirect_url = f"{settings.run.frontend_url.rstrip('/')}/?{urlencode(params)}"
        return RedirectResponse(url=redirect_url, status_code=302)

    return templates.TemplateResponse(
        "verification.html",
        {
            "request": request,
        },
    )
