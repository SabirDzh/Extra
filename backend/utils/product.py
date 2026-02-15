from typing import Annotated

from core.authentication.fastapi_users import current_active_user
from core.models.db_helper import db_helper
from core.models.user import User
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from utils.role import UserRole

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]


async def current_admin(
    current_user: Annotated[User, Depends(current_active_user)],
):
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    return current_user
