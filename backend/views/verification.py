from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
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
def verify_email(
    request: Request,
):
    token = request.query_params.get("token")
    if token:
        redirect_url = (
            f"{settings.run.frontend_url.rstrip('/')}/?{urlencode({'token': token})}"
        )
        return RedirectResponse(url=redirect_url, status_code=302)

    return templates.TemplateResponse(
        "verification.html",
        {
            "request": request,
        },
    )
