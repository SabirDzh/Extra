import json
import uuid
from typing import List

from core.models.faq import FAQ
from core.schemas.faq import FAQCreate, FAQUpdate
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.db import ensure_unique_field


async def get_faqs(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 20,
) -> List[FAQ]:
    stmt = select(FAQ).order_by(FAQ.order_index.asc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_faq(
    session: AsyncSession,
    faq_id: uuid.UUID,
) -> FAQ | None:
    return await session.get(FAQ, faq_id)


async def create_faq(
    session: AsyncSession,
    faq_in: FAQCreate,
) -> FAQ:
    # Check for duplicate question using utility
    await ensure_unique_field(
        session,
        FAQ,
        "question",
        faq_in.question,
        error_msg=f"FAQ with question '{faq_in.question}' already exists",
    )

    faq = FAQ(**faq_in.model_dump())
    session.add(faq)
    await session.commit()
    await session.refresh(faq)
    return faq


async def update_faq(
    session: AsyncSession,
    faq: FAQ,
    faq_update: FAQUpdate,
) -> FAQ:
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

    for field, value in patch.items():
        setattr(faq, field, value)

    await session.commit()
    await session.refresh(faq)
    return faq


async def delete_faq(
    session: AsyncSession,
    faq: FAQ,
) -> None:
    await session.delete(faq)
    await session.commit()


async def search_faqs(
    session: AsyncSession,
    q: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> List[FAQ]:
    stmt = select(FAQ)
    
    if q:
        if len(q) < 3:
            search_pattern = f"%{q}%"
            stmt = stmt.where(
                or_(
                    FAQ.question.ilike(search_pattern),
                    FAQ.answer.ilike(search_pattern),
                )
            ).order_by(FAQ.question.asc())
        else:
            stmt = stmt.where(
                or_(
                    FAQ.question.bool_op("%")(q),
                    FAQ.answer.bool_op("%")(q),
                )
            ).order_by(
                func.similarity(FAQ.question, q).desc(),
                func.similarity(FAQ.answer, q).desc(),
            )
            
    result = await session.execute(stmt.offset(offset).limit(limit))
    return result.scalars().all()


async def bulk_delete_faqs(
    session: AsyncSession,
    faq_ids: List[uuid.UUID],
) -> None:
    stmt = delete(FAQ).where(FAQ.id.in_(faq_ids))
    await session.execute(stmt)
    await session.commit()


# переделать, надо чтобы принимал помимо json еще эксель и csv
async def import_faqs_from_json(
    session: AsyncSession,
    file: UploadFile,
) -> dict:
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only JSON files are allowed")

    try:
        content = await file.read()
        items = json.loads(content)
        if not isinstance(items, list):
            raise ValueError("Root element must be a list")

        faqs = []
        imported_count = 0
        skipped_count = 0

        for item in items:
            if "question" not in item or "answer" not in item:
                continue

            q_text = item["question"]
            # Check for existing question in DB
            try:
                await ensure_unique_field(session, FAQ, "question", q_text)
            except HTTPException:
                skipped_count += 1
                continue

            faqs.append(
                FAQ(
                    question=q_text,
                    answer=item["answer"],
                    order_index=item.get("order_index", 0),
                    is_published=item.get("is_published", True),
                )
            )
            imported_count += 1

        if faqs:
            session.add_all(faqs)
            await session.commit()
            return {
                "detail": f"Successfully imported {imported_count} FAQ items. Skipped {skipped_count} duplicates."
            }
        return {"detail": "No new valid FAQ items found in file"}

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid file content: {str(e)}")
