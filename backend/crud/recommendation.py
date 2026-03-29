import csv
import io
import json
import uuid
from typing import List, Literal

import pandas as pd
from core.models.recommendation import Recommendation
from core.schemas.recommendation import (
    RecommendationCreate,
    RecommendationUpdate,
)
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import asc, delete, desc, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.db import ensure_unique_field


async def get_recommendation_admin(session: AsyncSession, recommendation_id: uuid.UUID):
    return await session.get(Recommendation, recommendation_id)


async def get_recommendation(session: AsyncSession, recommendation_id: uuid.UUID):
    stmt = select(
        Recommendation.id,
        Recommendation.title,
        Recommendation.description,
        Recommendation.created_at,
    ).where(Recommendation.id == recommendation_id)
    result = await session.execute(stmt)
    return result.first()


async def get_recommendations(
    session: AsyncSession,
    limit: int,
    offset: int,
    sorted: Literal["asc", "desc"],
    sorted_by: Literal["title", "created_at"],
):
    order_func = desc if sorted == "desc" else asc
    stmt = (
        select(
            Recommendation.id,
            Recommendation.title,
            Recommendation.created_at,
        )
        .limit(limit)
        .offset(offset)
        .order_by(order_func(getattr(Recommendation, sorted_by)))
    )
    result = await session.execute(stmt)
    return result.mappings().all()


async def create_recommendation(
    session: AsyncSession,
    recommendation_in: RecommendationCreate,
    admin_id: uuid.UUID,
):
    await ensure_unique_field(
        session,
        Recommendation,
        "title",
        recommendation_in.title,
        error_msg=f"Recomendation with title '{recommendation_in.title}' already exists",
    )
    recomendation = Recommendation(
        **recommendation_in.model_dump(),
        created_by=admin_id,
    )
    session.add(recomendation)
    await session.commit()
    await session.refresh(recomendation)
    return recomendation


async def update_recommendation(
    session: AsyncSession,
    recommendation_id: uuid.UUID,
    recommendation_in: RecommendationUpdate,
):
    patch = recommendation_in.model_dump(exclude_unset=True)
    if "title" in patch and patch["title"]:
        await ensure_unique_field(
            session,
            Recommendation,
            "title",
            patch["title"],
            exclude_id=recommendation_id,
            error_msg=f"Recomendation with title '{patch['title']}' already exists",
        )
    recommendation = await session.get(Recommendation, recommendation_id)
    if not recommendation:
        return None

    update_data = recommendation_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(recommendation, key, value)

    await session.commit()
    await session.refresh(recommendation)
    return recommendation


async def delete_recommendation(session: AsyncSession, recommendation_id: uuid.UUID):
    stmt = delete(Recommendation).where(Recommendation.id == recommendation_id)
    await session.execute(stmt)
    await session.commit()


async def delete_recommendations(
    session: AsyncSession, recommendations_list_id: list[uuid.UUID]
):
    stmt = delete(Recommendation).where(Recommendation.id.in_(recommendations_list_id))
    await session.execute(stmt)
    await session.commit()


async def delete_all_recommendations(session: AsyncSession):
    await session.execute(delete(Recommendation))
    await session.commit()


async def search_recommendations(
    session: AsyncSession,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    stmt = select(
        Recommendation.id,
        Recommendation.title,
        Recommendation.created_at,
    )

    if q and q.strip():
        q_str = q.strip()
        if len(q_str) < 2:
            search_pattern = f"%{q_str}%"
            stmt = stmt.where(
                or_(
                    Recommendation.title.ilike(search_pattern),
                    Recommendation.description.ilike(search_pattern),
                )
            ).order_by(Recommendation.title.asc())
        else:
            relevance = (
                func.similarity(Recommendation.title, q_str) * 2
                + func.similarity(Recommendation.description, q_str) * 0.5
            )
            search_pattern = f"%{q_str}%"
            stmt = stmt.where(
                or_(
                    Recommendation.title.bool_op("%")(q_str),
                    Recommendation.description.bool_op("%")(q_str),
                    Recommendation.title.ilike(search_pattern),
                    Recommendation.description.ilike(search_pattern),
                )
            ).order_by(relevance.desc())
    else:
        stmt = stmt.order_by(Recommendation.title.asc())

    result = await session.execute(stmt.offset(offset).limit(limit))
    return result.mappings().all()


def check_format(filename: str) -> str:
    filename = filename.lower()
    if not filename.endswith((".csv", ".xlsx", ".xls", ".json")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Разрешены только файлы форматов JSON, CSV и Excel (.xlsx, .xls)",
        )
    return filename


def parse_recommendation_json_file(contents: bytes) -> list[dict]:
    try:
        items = json.loads(contents.decode("utf-8"))
        if not isinstance(items, list):
            raise ValueError("Root element must be a list")
        return items
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON content: {str(e)}")


def parse_recommendation_csv_file(contents: bytes) -> list[dict]:
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл CSV должен быть в кодировке UTF-8",
        )

    recommendations_data = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        title = row.get("title", "").strip()
        description = row.get("description", "").strip()

        if title and description:
            recommendations_data.append(
                {
                    "title": title,
                    "description": description,
                }
            )

    return recommendations_data


def parse_recommendation_excel_file(contents: bytes) -> list[dict]:
    try:
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка чтения Excel файла: {str(e)}",
        )

    required_cols = {"title", "description"}
    actual_cols = {str(c).lower().strip() for c in df.columns}
    if not required_cols.issubset(actual_cols):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="В файле Excel отсутствуют обязательные колонки 'title' и/или 'description'",
        )

    df = df.fillna("")
    recommendations_data = []

    for index, row in df.iterrows():
        title = str(row.get("title", "")).strip()
        description = str(row.get("description", "")).strip()

        if title and description:
            recommendations_data.append(
                {
                    "title": title,
                    "description": description,
                }
            )

    return recommendations_data


async def import_recommendations(
    session: AsyncSession,
    file: UploadFile,
    admin_id: uuid.UUID,
) -> dict:
    filename = check_format(file.filename)

    try:
        contents = await file.read()

        if filename.endswith(".json"):
            items = parse_recommendation_json_file(contents)
        elif filename.endswith(".csv"):
            items = parse_recommendation_csv_file(contents)
        else:
            items = parse_recommendation_excel_file(contents)

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

        stmt = select(Recommendation.title).where(
            Recommendation.title.in_(incoming_titles)
        )
        existing_result = await session.execute(stmt)
        existing_titles = {t.lower() for t in existing_result.scalars().all()}

        new_recommendations = []
        for item in valid_items:
            if item["title"].lower() not in existing_titles:
                new_recommendations.append(
                    {
                        "title": item["title"],
                        "description": item["description"],
                        "created_by": admin_id,
                    }
                )

        if new_recommendations:
            await session.execute(insert(Recommendation), new_recommendations)
            await session.commit()
            return {
                "message": f"Успешно импортировано {len(new_recommendations)} новых рекомендаций."
            }
        else:
            return {
                "message": "Новых рекомендаций не найдено. Возможно, все записи уже существуют."
            }

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при импорте данных: {str(e)}",
        )
