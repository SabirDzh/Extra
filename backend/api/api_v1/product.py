import uuid
from typing import TYPE_CHECKING, Annotated

from core.config import settings
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.product import ProductCreate, ProductRead, ProductUpdate
from crud.product import (
    create_product,
    delete_product,
    get_product,
    get_products,
    search_product,
    update_product,
)
from fastapi import APIRouter, Depends, Query, status
from fastapi_cache import decorator
from sqlalchemy.ext.asyncio import AsyncSession
from utils.product import current_admin

router = APIRouter(
    prefix=settings.api.v1.product,
    tags=["Product"],
)

if TYPE_CHECKING:
    from core.models.product import Product

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
CurrentAdmin = Annotated[User, Depends(current_admin)]


@router.get("", response_model=list[ProductRead], status_code=status.HTTP_200_OK)
@decorator.cache(60)
async def get_list_products(session: Session, offset: int = 0, limit: int = 10):
    return await get_products(session, offset, limit)


@router.get("/{product_id}", response_model=ProductRead, status_code=status.HTTP_200_OK)
@decorator.cache(60)
async def get_product_by_id(
    product_id: uuid.UUID,
    session: Session,
    # background_tasks: BackgroundTasks,
    # redis: Redis,
):
    # background_tasks.add_task(increment_product_view, redis, product_id)
    return await get_product(session, product_id)


@router.get(
    "/search/search_query",
    response_model=list[ProductRead],
    status_code=status.HTTP_200_OK,
)
@decorator.cache(60)
async def get_search_product(
    session: Session,
    search_query: str | None = Query(None, description="Search request", min_length=1),
    limit: int = 10,
    offset: int = 0,
):
    return await search_product(session, search_query, limit)


@router.post("", status_code=status.HTTP_201_CREATED)
async def product_created(
    product: ProductCreate,
    session: Session,
    admin: CurrentAdmin,
):
    return await create_product(session, product)


@router.patch(
    "/{product_id}", response_model=ProductRead, status_code=status.HTTP_200_OK
)
async def product_update(
    product: ProductUpdate,
    product_id: uuid.UUID,
    session: Session,
    admin: CurrentAdmin,
):
    return await update_product(session, product_id, product)


@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
async def product_delete(
    product_id: uuid.UUID,
    session: Session,
    admin: CurrentAdmin,
):
    await delete_product(session, product_id)


# @router.get(
#     "/popular",
#     response_model=list[ProductRead],
#     status_code=status.HTTP_200_OK,
# )
# async def get_popular_product(
#     session: Session,
#     redis: Redis,
# ):
#     top_product_ids = await redis.zrevrange("product:views:all_time", 0, 4)

#     if not top_product_ids:
#         return []

#     stmt = select(Product).where(Product.id.in_(top_product_ids))
#     result = await session.execute(stmt)
#     products = result.scalars().all()

#     products_map = {str(p.id): p for p in products}
#     sorted_products = [
#         products_map[pid] for pid in top_product_ids if pid in products_map
#     ]
#     return sorted_products


# TODO add sorting support
