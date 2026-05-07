import uuid
from typing import Annotated, Literal

import Services.recommendation as recommendation_crud
from core.authentication.fastapi_users import current_active_user, current_optional_user
from core.config import settings
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.base import ListParams
from core.schemas.recommendation import (
    RecommendationCreate,
    RecommendationListRead,
    RecommendationRead,
    RecommendationReadAdmin,
    RecommendationUpdate,
)
from Repository.search_engine import SearchSort
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.authorization import current_admin

router = APIRouter(
    prefix=settings.api.v1.recommendations,
    tags=["Recommendation"],
)


Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
AdminUser = Annotated[User, Depends(current_admin)]
IsUser = Annotated[User, Depends(current_active_user)]
OptionalUser = Annotated[User | None, Depends(current_optional_user)]


@router.get("", response_model=list[RecommendationListRead])
async def get_recomendations(
    session: Session,
    limit: int | None = Query(None, ge=1, le=9000),
    page: int | None = Query(None, ge=1),
    sorted: Literal["asc", "desc"] = "asc",
    sorted_by: Literal["title", "created_at", "description"] = "title",
):
    # If client sends no pagination params, return all records.
    if limit is None and page is None:
        calculated_limit = None
        offset = 0
    else:
        calculated_limit = limit or 9000
        calculated_page = page or 1
        offset = (calculated_page - 1) * calculated_limit

    return await recommendation_crud.get_recommendations(
        session,
        calculated_limit,
        offset,
        sorted,
        sorted_by,
    )


@router.get("/search", response_model=list[RecommendationListRead])
async def search_recomendations(
    session: Session,
    query_param: Annotated[ListParams, Depends()],
    q: str | None = None,
    search_in: Literal["title", "description", "all"] = Query("all"),
    sort: SearchSort = Query("alphabet_asc"),
):
    return await recommendation_crud.search_recommendations(
        session,
        q=q,
        limit=query_param.limit,
        offset=query_param.offset,
        search_in=search_in,
        sort=sort,
    )


@router.get("/{recommendation_id}/admin", response_model=RecommendationReadAdmin)
async def get_recommendation_admin(
    session: Session, recommendation_id: uuid.UUID, admin: AdminUser
):
    result = await recommendation_crud.get_recommendation_admin(
        session, recommendation_id
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found"
        )
    return result


@router.get("/{recommendation_id}", response_model=RecommendationRead)
async def get_recommendation(session: Session, recommendation_id: uuid.UUID):
    result = await recommendation_crud.get_recommendation(session, recommendation_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found"
        )
    return result


@router.post("", response_model=RecommendationRead, status_code=status.HTTP_201_CREATED)
async def create_recomendation(
    session: Session, recommendation_in: RecommendationCreate, admin: AdminUser
):
    return await recommendation_crud.create_recommendation(
        session, recommendation_in, admin.id
    )


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_recommendations(
    session: Session, admin: AdminUser, file: UploadFile = File()
):
    return await recommendation_crud.import_recommendations(session, file, admin.id)


@router.patch("/{recommendation_id}", response_model=RecommendationRead)
async def update_recomendation(
    session: Session,
    recommendation_id: uuid.UUID,
    recommendation_in: RecommendationUpdate,
    admin: AdminUser,
):
    result = await recommendation_crud.update_recommendation(
        session, recommendation_id, recommendation_in
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found"
        )
    return result


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recomendations(
    session: Session,
    recommendation_list_id: Annotated[list[uuid.UUID], Query()],
    admin: AdminUser,
):
    return await recommendation_crud.delete_recommendations(
        session, recommendation_list_id
    )


@router.delete("/all", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_recomendation(session: Session, admin: AdminUser):
    return await recommendation_crud.delete_all_recommendations(session)


@router.delete("/{recommendation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recomendation(
    session: Session, recommendation_id: uuid.UUID, admin: AdminUser
):
    return await recommendation_crud.delete_recommendation(session, recommendation_id)
