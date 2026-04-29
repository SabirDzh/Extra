import uuid

from core.models.term import Term
from core.schemas.base import PaginationParams
from core.schemas.term import TermRequest
from fastapi import HTTPException, UploadFile, status
from Repository import term as repo
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_terms(session: AsyncSession, pagination: PaginationParams):
    return await repo.get_terms(session, pagination)


async def get_term(session: AsyncSession, term_id: uuid.UUID):
    return await repo.get_term(session, term_id)


async def get_term_by_title(session: AsyncSession, title: str):
    return await repo.get_term_by_title(session, title)


async def search_terms(
    session: AsyncSession,
    q: str | None,
    pagination: PaginationParams,
):
    return await repo.search_terms(session, q, pagination)


async def create_term(session: AsyncSession, term: TermRequest):
    return await repo.create_term(session, term)


async def update_term(
    session: AsyncSession,
    term_id: uuid.UUID,
    term: TermRequest,
):
    patch = term.model_dump(exclude_unset=True)
    if "title" in patch and patch["title"]:
        existing = await session.execute(
            select(Term).where(
                func.lower(Term.title) == patch["title"].lower(), Term.id != term_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Term already exists",
            )
    return await repo.update_term(session, term_id, term)


async def delete_term(session: AsyncSession, term_id: uuid.UUID):
    await repo.delete_term(session, term_id)


async def delete_terms(session: AsyncSession, terms_id: list[uuid.UUID]):
    return await repo.delete_terms(session, terms_id)


async def delete_all_terms(session: AsyncSession):
    return await repo.delete_all_terms(session)


async def import_terms(session: AsyncSession, file: UploadFile):
    return await repo.import_terms(session, file)
