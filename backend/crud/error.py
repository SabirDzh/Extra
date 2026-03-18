import csv
import io
import json
import uuid
from typing import List, Literal

import pandas as pd
from core.models.error import Error
from core.schemas.error import ErrorCreate, ErrorUpdate
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.db import ensure_unique_field


async def get_errors(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    sorted: Literal["asc", "desc"] = "asc",
) -> List[Error]:
    stmt = select(Error).offset(offset).limit(limit).order_by(
        Error.order_index.asc() if sorted == "asc" else Error.order_index.desc()
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_error(
    session: AsyncSession,
    error_id: uuid.UUID,
) -> Error | None:
    return await session.get(Error, error_id)


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

    error = Error(**error_in.model_dump(), created_by=user_id)
    session.add(error)
    await session.commit()
    await session.refresh(error)
    return error


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

    for field, value in patch.items():
        setattr(error, field, value)

    await session.commit()
    await session.refresh(error)
    return error


async def delete_error(
    session: AsyncSession,
    error: Error,
) -> None:
    await session.delete(error)
    await session.commit()


async def delete_errors(
    session: AsyncSession,
    error_ids: List[uuid.UUID],
) -> None:
    stmt = delete(Error).where(Error.id.in_(error_ids))
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


def parse_error_json_file(contents: bytes) -> list[dict]:
    try:
        items = json.loads(contents.decode("utf-8"))
        if not isinstance(items, list):
            raise ValueError("Root element must be a list")
        return items
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON content: {str(e)}")


def parse_error_csv_file(contents: bytes) -> list[dict]:
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл CSV должен быть в кодировке UTF-8",
        )

    errors_data = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        title = row.get("title", "").strip()
        description = row.get("description", "").strip()

        if title and description:
            order_index = 0
            if "order_index" in row and row["order_index"].isdigit():
                order_index = int(row["order_index"])

            is_published = True
            if "is_published" in row:
                val = row["is_published"].strip().lower()
                if val in ["false", "0", "no"]:
                    is_published = False

            errors_data.append(
                {
                    "title": title,
                    "description": description,
                    "order_index": order_index,
                    "is_published": is_published,
                }
            )
    return errors_data


def parse_error_excel_file(contents: bytes) -> list[dict]:
    df = pd.read_excel(io.BytesIO(contents))

    if "title" not in df.columns or "description" not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="В файле Excel отсутствуют обязательные колонки 'title' и/или 'description'",
        )

    df = df.fillna("")
    errors_data = []

    for index, row in df.iterrows():
        title = str(row.get("title", "")).strip()
        description = str(row.get("description", "")).strip()

        if title and description:
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

            errors_data.append(
                {
                    "title": title,
                    "description": description,
                    "order_index": order_index,
                    "is_published": is_published,
                }
            )

    return errors_data


async def import_errors(
    session: AsyncSession,
    file: UploadFile,
    user_id: uuid.UUID,
) -> dict:
    filename = check_format(file.filename)

    try:
        contents = await file.read()

        if filename.endswith(".json"):
            items = parse_error_json_file(contents)
        elif filename.endswith(".csv"):
            items = parse_error_csv_file(contents)
        else:
            items = parse_error_excel_file(contents)

        if not items:
            return {"message": "Файл пуст или не содержит валидных данных для импорта"}

        # Exclude duplicates
        incoming_titles = []
        valid_items = []
        for item in items:
            if "title" in item and "description" in item:
                t = item["title"].strip()
                if t:
                    incoming_titles.append(t)
                    valid_items.append(item)

        if not valid_items:
            return {"message": "Не найдено валидных заголовков в файле."}

        stmt = select(Error.title).where(Error.title.in_(incoming_titles))
        existing_result = await session.execute(stmt)
        existing_titles = {t.lower() for t in existing_result.scalars().all()}

        new_errors = []
        for item in valid_items:
            if item["title"].lower() not in existing_titles:
                new_errors.append(
                    {
                        "title": item["title"],
                        "description": item["description"],
                        "order_index": item.get("order_index", 0),
                        "is_published": item.get("is_published", True),
                        "created_by": user_id,
                    }
                )
                existing_titles.add(item["title"].lower())

        if not new_errors:
            return {
                "message": f"Найдено {len(valid_items)} записей, но все они уже существуют."
            }

        stmt_insert = insert(Error).values(new_errors)
        await session.execute(stmt_insert)
        await session.commit()

        return {
            "msg": f"Успешно импортировано ошибок: {len(new_errors)}. Пропущено дубликатов: {len(valid_items) - len(new_errors)}.",
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
