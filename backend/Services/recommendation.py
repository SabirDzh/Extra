import uuid
from typing import Literal

from core.models.recommendation import Recommendation
from core.schemas.recommendation import RecommendationCreate, RecommendationUpdate
from fastapi import UploadFile
from Repository import recommendation as repo
from sqlalchemy.ext.asyncio import AsyncSession
from Repository.common import ensure_unique_field


async def get_recommendation_admin(session: AsyncSession, recommendation_id: uuid.UUID):
    return await repo.get_recommendation_admin(session, recommendation_id)


async def get_recommendation(session: AsyncSession, recommendation_id: uuid.UUID):
    return await repo.get_recommendation(session, recommendation_id)


async def get_recommendations(
    session: AsyncSession,
    limit: int | None,
    offset: int,
    sorted: Literal["asc", "desc"],
    sorted_by: Literal["title", "created_at", "description"],
):
    return await repo.get_recommendations(session, limit, offset, sorted, sorted_by)


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
    return await repo.create_recommendation(session, recommendation_in, admin_id)


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
    return await repo.update_recommendation(session, recommendation_id, recommendation_in)


async def delete_recommendation(session: AsyncSession, recommendation_id: uuid.UUID):
    await repo.delete_recommendation(session, recommendation_id)


async def delete_recommendations(
    session: AsyncSession, recommendations_list_id: list[uuid.UUID]
):
    await repo.delete_recommendations(session, recommendations_list_id)


async def delete_all_recommendations(session: AsyncSession):
    await repo.delete_all_recommendations(session)


async def search_recommendations(
    session: AsyncSession,
    q: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    return await repo.search_recommendations(session, q, limit, offset)


async def import_recommendations(
    session: AsyncSession, file: UploadFile, admin_id: uuid.UUID
):
    return await repo.import_recommendations(session, file, admin_id)
