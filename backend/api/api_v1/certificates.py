import uuid
from typing import Annotated

from core.authentication.fastapi_users import current_active_user
from core.config import settings
from core.models.db_helper import db_helper
from core.models.user import User
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix=settings.api.v1.certificates,
    tags=["Certificates"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]


@router.get("/")
async def get_certificate():
    pass


@router.get("/{certificate_id}/download")
async def download_certificate():
    pass


@router.post("/generate/{course_id}")
async def generate_certificate(
    course_id: uuid.UUID,
    session: Session,
    user: User = Depends(current_active_user),
):
    "Напиши не заглушку а реальный запрос проверки"
    pass
