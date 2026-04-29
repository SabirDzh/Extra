from core.authentication.fastapi_users import current_active_user
from core.models.user import User
from fastapi import Depends, HTTPException, status

from Domain.Enums.user_role import UserRole


async def current_admin(
    current_user: User = Depends(current_active_user),
):
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    return current_user
