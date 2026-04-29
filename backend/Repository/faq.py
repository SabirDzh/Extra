import csv
import io
import json
import uuid
from typing import List

import pandas as pd
from core.models.faq import FAQ
from core.schemas.faq import FAQCreate, FAQUpdate
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, func, insert, or_, select
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
    patch = faq_update.model_dump(exclude_unset=True)

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
        if len(q) < 2:
            search_pattern = f"%{q}%"
            stmt = stmt.where(
                or_(
                    FAQ.question.ilike(search_pattern),
                    FAQ.answer.ilike(search_pattern),
                )
            ).order_by(FAQ.question.asc())
        else:
            relevance = (
                func.similarity(FAQ.question, q) * 2
                + func.similarity(FAQ.answer, q) * 0.5
            )
            search_pattern = f"%{q}%"
            stmt = stmt.where(
                or_(
                    FAQ.question.bool_op("%")(q),
                    FAQ.answer.bool_op("%")(q),
                    FAQ.question.ilike(search_pattern),
                    FAQ.answer.ilike(search_pattern),
                )
            ).order_by(relevance.desc())

    result = await session.execute(stmt.offset(offset).limit(limit))
    return result.scalars().all()


async def bulk_delete_faqs(
    session: AsyncSession,
    faq_ids: List[uuid.UUID],
) -> None:
    stmt = delete(FAQ).where(FAQ.id.in_(faq_ids))
    await session.execute(stmt)
    await session.commit()


async def delete_all_faqs(session: AsyncSession) -> None:
    stmt = delete(FAQ)
    await session.execute(stmt)
    await session.commit()


def check_format(filename: str) -> str:
    filename = filename.lower()
    if not filename.endswith((".csv", ".xlsx", ".xls", ".json")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Разрешены только файлы форматов JSON, CSV и Excel (.xlsx, .xls)",
        )
    return filename


def parse_faq_json_file(contents: bytes) -> list[dict]:
    try:
        items = json.loads(contents.decode("utf-8"))
        if not isinstance(items, list):
            raise ValueError("Root element must be a list")
        return items
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON content: {str(e)}")


def parse_faq_csv_file(contents: bytes) -> list[dict]:
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл CSV должен быть в кодировке UTF-8",
        )

    faqs_data = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        question = row.get("question", "").strip()
        answer = row.get("answer", "").strip()

        if question and answer:
            order_index = 0
            if "order_index" in row and row["order_index"].isdigit():
                order_index = int(row["order_index"])

            is_published = True
            if "is_published" in row:
                val = row["is_published"].strip().lower()
                if val in ["false", "0", "no"]:
                    is_published = False

            faqs_data.append(
                {
                    "question": question,
                    "answer": answer,
                    "order_index": order_index,
                    "is_published": is_published,
                }
            )
    return faqs_data


def parse_faq_excel_file(contents: bytes) -> list[dict]:
    df = pd.read_excel(io.BytesIO(contents))

    if "question" not in df.columns or "answer" not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="В файле Excel отсутствуют обязательные колонки 'question' и/или 'answer'",
        )

    df = df.fillna("")
    faqs_data = []

    for index, row in df.iterrows():
        question = str(row.get("question", "")).strip()
        answer = str(row.get("answer", "")).strip()

        if question and answer:
            order_index = 0
            if "order_index" in df.columns:
                val = row.get("order_index", "")
                if str(val).isdigit() or isinstance(val, (int, float)):
                    try:
                        order_index = int(val)
                    except ValueError:
                        pass

            is_published = True
            if "is_published" in df.columns:
                val = str(row.get("is_published", "")).strip().lower()
                if val in ["false", "0", "no"]:
                    is_published = False

            faqs_data.append(
                {
                    "question": question,
                    "answer": answer,
                    "order_index": order_index,
                    "is_published": is_published,
                }
            )

    return faqs_data


async def import_faqs(
    session: AsyncSession,
    file: UploadFile,
) -> dict:
    filename = check_format(file.filename)

    try:
        contents = await file.read()

        if filename.endswith(".json"):
            items = parse_faq_json_file(contents)
        elif filename.endswith(".csv"):
            items = parse_faq_csv_file(contents)
        else:
            items = parse_faq_excel_file(contents)

        if not items:
            return {"message": "Файл пуст или не содержит валидных данных для импорта"}


        incoming_questions = []
        valid_items = []
        for item in items:
            if "question" in item and "answer" in item:
                q = item["question"].strip()
                if q:
                    incoming_questions.append(q)
                    valid_items.append(item)

        if not valid_items:
            return {"message": "Не найдено валидных вопросов в файле."}

        stmt = select(FAQ.question).where(FAQ.question.in_(incoming_questions))
        existing_result = await session.execute(stmt)

        existing_questions = {q.lower() for q in existing_result.scalars().all()}

        new_faqs = []
        for item in valid_items:
            if item["question"].lower() not in existing_questions:
                new_faqs.append(
                    {
                        "question": item["question"],
                        "answer": item["answer"],
                        "order_index": item.get("order_index", 0),
                        "is_published": item.get("is_published", True),
                    }
                )

                existing_questions.add(item["question"].lower())

        if not new_faqs:
            return {
                "message": f"Найдено {len(valid_items)} записей, но все они уже существуют."
            }

        stmt_insert = insert(FAQ).values(new_faqs)
        await session.execute(stmt_insert)
        await session.commit()

        return {
            "msg": f"Успешно импортировано FAQ: {len(new_faqs)}. Пропущено дубликатов: {len(valid_items) - len(new_faqs)}.",
            "status": "OK",
        }

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при импорте: {str(e)}",
        )
