import uuid
from typing import List, Literal

from core.models.error import Error
from core.schemas.error import ErrorCreate, ErrorUpdate
from fastapi import UploadFile
from Repository import error as repo
from sqlalchemy.ext.asyncio import AsyncSession
from Repository.common import ensure_unique_field


async def get_errors(
    session: AsyncSession,
    limit: int | None = None,
    offset: int = 0,
    sorted: Literal["asc", "desc"] = "asc",
) -> List[Error]:
    return await repo.get_errors(session, limit, offset, sorted)


async def get_error(session: AsyncSession, error_id: uuid.UUID) -> Error | None:
    return await repo.get_error(session, error_id)


async def search_errors(
    session: AsyncSession,
    q: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> List[Error]:
    return await repo.search_errors(session, q, limit, offset)


async def create_error(
    session: AsyncSession,
    error_in: ErrorCreate,
    user_id: uuid.UUID,
) -> Error:
    await ensure_unique_field(
        session,
        Error,
        "title",
        error_in.title,
        error_msg=f"Error with title '{error_in.title}' already exists",
    )
    return await repo.create_error(session, error_in, user_id)


async def update_error(
    session: AsyncSession,
    error: Error,
    error_update: ErrorUpdate,
) -> Error:
    patch = error_update.model_dump(exclude_unset=True)
    if "title" in patch and patch["title"]:
        await ensure_unique_field(
            session,
            Error,
            "title",
            patch["title"],
            exclude_id=error.id,
            error_msg=f"Error with title '{patch['title']}' already exists",
        )
    return await repo.update_error(session, error, error_update)


async def delete_error(session: AsyncSession, error: Error) -> None:
    await repo.delete_error(session, error)


async def delete_errors(session: AsyncSession, error_ids: List[uuid.UUID]) -> None:
    await repo.delete_errors(session, error_ids)


async def delete_all_errors(session: AsyncSession) -> None:
    await repo.delete_all_errors(session)


async def import_errors(session: AsyncSession, file: UploadFile, user_id: uuid.UUID):
    return await repo.import_errors(session, file, user_id)
