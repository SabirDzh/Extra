import uuid
from typing import Annotated

from core.authentication.fastapi_users import current_active_user
from core.models.user import User
from fastapi import Depends
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession


async def reset_password(
    session: AsyncSession,
    user_id: uuid.UUID,
    new_password,
    auth: Annotated[User, Depends(current_active_user)],
) -> None:
    # TODO new_password = | хэшировать перед апдейтом пароля пользователя
    result = update(User).values(hashed_password=new_password).where(User.id == user_id)
    await session.execute(result)
    await session.commit()
