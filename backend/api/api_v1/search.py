from typing import Annotated, Literal

from core.authentication.fastapi_users import current_optional_user
from core.config import settings
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.search import GlobalSearchResponse
from Services import search as search_crud
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix=settings.api.v1.search,
    tags=["Global Search"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]


@router.get("/", response_model=GlobalSearchResponse)
async def global_search(
    db: Session,
    q: str | None = Query(None, description="Search query"),
    limit: int = Query(5, ge=1, le=50, description="Limit per category"),
    sort_by: Annotated[
        Literal["title", "description", "all"],
        Query(
            description=(
                "Field scope for matching. "
                "For non-empty q ranking is relevance-first; for empty q this works as browse scope."
            )
        ),
    ] = "all",
    order: Annotated[
        Literal["asc", "desc"],
        Query(
            description=(
                "Browse order for empty q. "
                "For non-empty q this does not override relevance ranking."
            )
        ),
    ] = "asc",
    user: User | None = Depends(current_optional_user),
):
    results = await search_crud.global_search_entities(
        db,
        q=q,
        limit_per_category=limit,
        search_in=sort_by,
        sort="alphabet_desc" if order == "desc" else "alphabet_asc",
        user_role=user.role if user else None,
    )
    return GlobalSearchResponse(**results)
