import uuid
from typing import Any, Type

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def ensure_unique_field(
    session: AsyncSession,
    model: Type[Any],
    field_name: str,
    value: str,
    exclude_id: uuid.UUID | None = None,
    error_msg: str | None = None,
):
    field = getattr(model, field_name)
    stmt = select(model).where(func.lower(field) == value.lower())

    if exclude_id:
        stmt = stmt.where(model.id != exclude_id)

    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        if not error_msg:
            error_msg = f"{model.__name__} with {field_name} '{value}' already exists"

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_msg,
        )
