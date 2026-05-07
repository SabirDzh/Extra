import uuid
from typing import List

from core.models.faq import FAQ
from core.schemas.faq import FAQCreate, FAQUpdate
from fastapi import UploadFile
from Repository import faq as repo
from Repository.search_engine import SearchIn, SearchSort
from sqlalchemy.ext.asyncio import AsyncSession
from Repository.common import ensure_unique_field


async def get_faqs(session: AsyncSession, offset: int = 0, limit: int = 20) -> List[FAQ]:
    return await repo.get_faqs(session, offset, limit)


async def get_faq(session: AsyncSession, faq_id: uuid.UUID) -> FAQ | None:
    return await repo.get_faq(session, faq_id)


async def create_faq(session: AsyncSession, faq_in: FAQCreate) -> FAQ:
    await ensure_unique_field(
        session,
        FAQ,
        "question",
        faq_in.question,
        error_msg=f"FAQ with question '{faq_in.question}' already exists",
    )
    return await repo.create_faq(session, faq_in)


async def update_faq(session: AsyncSession, faq: FAQ, faq_update: FAQUpdate) -> FAQ:
    patch = faq_update.model_dump(exclude_unset=True)
    if "question" in patch and patch["question"]:
        await ensure_unique_field(
            session,
            FAQ,
            "question",
            patch["question"],
            exclude_id=faq.id,
            error_msg=f"FAQ with question '{patch['question']}' already exists",
        )
    return await repo.update_faq(session, faq, faq_update)


async def delete_faq(session: AsyncSession, faq: FAQ) -> None:
    await repo.delete_faq(session, faq)


async def search_faqs(
    session: AsyncSession,
    q: str | None = None,
    offset: int = 0,
    limit: int = 20,
    search_in: SearchIn = "all",
    sort: SearchSort = "alphabet_asc",
):
    return await repo.search_faqs(session, q, offset, limit, search_in, sort)


async def bulk_delete_faqs(session: AsyncSession, faq_ids: List[uuid.UUID]) -> None:
    await repo.bulk_delete_faqs(session, faq_ids)


async def delete_all_faqs(session: AsyncSession) -> None:
    await repo.delete_all_faqs(session)


async def import_faqs(session: AsyncSession, file: UploadFile):
    return await repo.import_faqs(session, file)
