from core.config import settings
from fastapi import APIRouter, status
from pydantic import EmailStr

router = APIRouter(
    prefix=settings.api.v1.auth,
    tags=["Auth"],
)


@router.post("/email", status_code=status.HTTP_200_OK)
async def send_email_message(user_email: EmailStr, send_user: EmailStr):
    return {"message": "send"}
