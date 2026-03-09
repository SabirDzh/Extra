import json
import uuid
from typing import List

from core.models.faq import FAQ
from core.schemas.faq import FAQCreate, FAQUpdate
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


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
    for field, value in faq_update.model_dump(exclude_unset=True).items():
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
        for item in items:
            if "question" not in item or "answer" not in item:
                continue
            faqs.append(
                FAQ(
                    question=item["question"],
                    answer=item["answer"],
                    order_index=item.get("order_index", 0),
                    is_published=item.get("is_published", True),
                )
            )

        if faqs:
            session.add_all(faqs)
            await session.commit()
            return {"detail": f"Successfully imported {len(faqs)} FAQ items"}
        return {"detail": "No valid FAQ items found in file"}

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid file content: {str(e)}")
