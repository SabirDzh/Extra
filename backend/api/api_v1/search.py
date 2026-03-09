from typing import Annotated

from core.config import settings
from core.models.db_helper import db_helper
from core.schemas.search import GlobalSearchResponse
from crud import search as search_crud
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
):
    results = await search_crud.global_search_entities(
        db, q=q, limit_per_category=limit
    )
    return GlobalSearchResponse(**results)
