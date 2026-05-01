import csv
import io
import uuid
from typing import Literal

import pandas as pd
from core.models.term import Term
from core.schemas.base import PaginationParams
from core.schemas.term import TermRequest
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession


async def get_terms(
    session: AsyncSession,
    pagination: PaginationParams,
    sorted: Literal["asc", "desc"] = "asc",
):
    order_by_title = (
        func.lower(Term.title).desc() if sorted == "desc" else func.lower(Term.title).asc()
    )
    stmt = (
        select(Term)
        .order_by(order_by_title)
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    result = await session.scalars(stmt)
    return result.all()


async def get_term(
    session: AsyncSession,
    term_id: uuid.UUID,
):
    return await session.get(Term, term_id)


async def get_term_by_title(
    session: AsyncSession,
    title: str,
):
    stmt = select(Term).where(func.lower(Term.title) == title.lower())
    result = await session.execute(stmt)
    return result.first()


async def search_terms(
    session: AsyncSession,
    q: str | None,
    pagination: PaginationParams,
):
    query = select(Term)
    if q:
        if len(q) < 2:
            search_pattern = f"%{q}%"
            query = query.where(
                (Term.title.ilike(search_pattern))
                | (Term.description.ilike(search_pattern))
            )
            query = query.order_by(Term.title.asc())
        else:
            relevance = (
                func.similarity(Term.title, q) * 2
                + func.similarity(Term.description, q) * 0.5
            )
            search_pattern = f"%{q}%"
            query = query.where(
                (Term.title.bool_op("%")(q))
                | (Term.description.bool_op("%")(q))
                | (Term.title.ilike(search_pattern))
                | (Term.description.ilike(search_pattern))
            )
            query = query.order_by(relevance.desc())
    else:
        query = query.order_by(Term.title.asc())

    query = query.offset(pagination.offset).limit(pagination.limit)
    result = await session.execute(query)
    return result.scalars().all()


async def create_term(
    session: AsyncSession,
    term: TermRequest,
):
    db_term = Term(**term.model_dump())
    session.add(db_term)
    await session.commit()
    await session.refresh(db_term)
    return db_term


async def update_term(
    session: AsyncSession,
    term_id: uuid.UUID,
    term: TermRequest,
):
    patch = term.model_dump(exclude_unset=True)
    if not patch:
        return await get_term(session, term_id)

    stmt = update(Term).values(**patch).where(Term.id == term_id).returning(Term)
    result = await session.execute(stmt)
    await session.commit()

    return result.scalar_one_or_none()


async def delete_term(
    session: AsyncSession,
    term_id: uuid.UUID,
):
    term = await get_term(session, term_id)
    if term is not None:
        await session.delete(term)
        await session.commit()


async def delete_terms(session: AsyncSession, terms_id: list[uuid.UUID]):
    stmt = delete(Term).where(Term.id.in_(terms_id))
    await session.execute(stmt)
    await session.commit()


async def delete_all_terms(session: AsyncSession):
    stmt = delete(Term)
    await session.execute(stmt)
    await session.commit()


def check_format(filename: str) -> str:
    filename = filename.lower()
    if not filename.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Разрешены только файлы форматов CSV и Excel (.xlsx, .xls)",
        )
    return filename


def parse_csv_file(contents: bytes) -> list[dict]:
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл CSV должен быть в кодировке UTF-8",
        )

    terms_data = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        title = row.get("title", "")
        description = row.get("description", "")

        if title and title.strip():
            terms_data.append(
                {
                    "title": title.strip(),
                    "description": description.strip() if description else "",
                }
            )
    return terms_data


def parse_excel_file(contents: bytes) -> list[dict]:
    df = pd.read_excel(io.BytesIO(contents))

    if "title" not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="В файле Excel отсутствует обязательная колонка 'title'",
        )

    df = df.fillna("")
    terms_data = []

    for index, row in df.iterrows():
        title = str(row.get("title", "")).strip()
        description = str(row.get("description", "")).strip()

        if title:
            terms_data.append({"title": title, "description": description})

    return terms_data


async def import_terms(session: AsyncSession, file: UploadFile):
    filename = check_format(file.filename)

    try:
        contents = await file.read()

        if filename.endswith(".csv"):
            terms_data = parse_csv_file(contents)
        else:
            terms_data = parse_excel_file(contents)

        if not terms_data:
            return {"message": "Файл пуст или не содержит валидных данных для импорта"}

        stmt = insert(Term).values(terms_data)
        await session.execute(stmt)
        await session.commit()

        return {
            "msg": f"Успешно импортировано терминов: {len(terms_data)}",
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
