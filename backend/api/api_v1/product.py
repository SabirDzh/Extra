import uuid
from typing import Annotated, Literal

from core.config import settings
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.base import PaginationParams
from core.schemas.product import (
    ProductCreate,
    ProductListRead,
    ProductRead,
    ProductSummaryInfo,
    ProductUpdate,
)
from crud import product as product_crud
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi_cache.decorator import cache
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from utils.analytics import (
    get_multiple_product_views,
    get_product_views,
    get_top_product_ids,
    track_product_view,
)
from utils.product import current_admin

from api.dependencies.redis import get_redis

router = APIRouter(
    prefix=settings.api.v1.product,
    tags=["Products"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
AdminUser = Annotated[User, Depends(current_admin)]
RedisDep = Annotated[Redis, Depends(get_redis)]


def _get_client_identifier(request: Request) -> str:
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "id"):
        return str(user.id)

    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/", response_model=list[ProductListRead])
@cache(expire=60)
async def list_products(
    db: Session,
    redis: RedisDep,
    pagination: PaginationParams = Depends(),
    sort_by: Literal["title", "created_at", "description"] = Query("title"),
    order: Literal["asc", "desc"] = Query("asc"),
    features: list[str] | None = Query(
        None, description="Filter by product attributes (e.g. 'Модуль Wi-Fi')"
    ),
):
    products = await product_crud.get_products(
        db,
        offset=pagination.offset,
        limit=pagination.limit,
        sort_by=sort_by,
        order=order,
        features=features,
    )

    return products


@router.get("/search", response_model=list[ProductListRead])
@cache(expire=60)
async def search_products(
    db: Session,
    redis: RedisDep,
    pagination: PaginationParams = Depends(),
    q: str | None = Query(None, description="Search query"),
    sort_by: Literal["title", "created_at", "description"] = Query("title"),
    order: Literal["asc", "desc"] = Query("asc"),
    features: list[str] | None = Query(
        None, description="Filter by product attributes"
    ),
):
    products = await product_crud.search_products(
        db,
        q=q,
        offset=pagination.offset,
        limit=pagination.limit,
        sort_by=sort_by,
        order=order,
        features=features,
    )

    return products


@router.post("/", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    db: Session,
    admin: AdminUser,
    redis: RedisDep,
):
    product = await product_crud.create_product(db, data)
    product.views = 0
    await redis.zadd("products:popularity", {str(product.id): 0})
    return product


@router.delete("/all/clear", status_code=status.HTTP_200_OK)
async def clear_all_products(
    db: Session,
    admin: AdminUser,
    redis: RedisDep,
):
    """Очищает всю таблицу товаров и сбрасывает рейтинги в Redis."""
    count = await product_crud.delete_all_products(db)

    try:
        keys = await redis.keys("product:*:unique_views")
        if keys:
            await redis.delete(*keys)
        await redis.delete("products:popularity")
    except Exception:
        pass

    return {
        "msg": f"Успешно удалено товаров: {count}. Данные в Redis сброшены.",
        "status": "OK",
    }


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: uuid.UUID,
    db: Session,
    redis: RedisDep,
    request: Request,
):
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )


    identifier = _get_client_identifier(request)
    await track_product_view(redis, product_id, identifier)


    views = await get_product_views(redis, product_id)
    product.views = views

    return product


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID,
    data: ProductUpdate,
    db: Session,
    admin: AdminUser,
    redis: RedisDep,
):
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    updated_product = await product_crud.update_product(db, product, data)
    updated_product.views = await get_product_views(redis, product_id)
    return updated_product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: uuid.UUID,
    db: Session,
    admin: AdminUser,
    redis: RedisDep,
):
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    await product_crud.delete_product(db, product)

    try:
        await redis.delete(f"product:{product_id}:unique_views")
        await redis.zrem("products:popularity", str(product_id))
    except Exception:
        pass


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_products(
    products_id: Annotated[list[uuid.UUID], Query()],
    db: Session,
    admin: AdminUser,
    redis: RedisDep,
):
    await product_crud.delete_products(db, products_id)
    if products_id:
        keys = [f"product:{pid}:unique_views" for pid in products_id]
        try:
            await redis.delete(*keys)
            await redis.zrem("products:popularity", *[str(pid) for pid in products_id])
        except Exception:
            pass


@router.get("/summary/", response_model=list[ProductSummaryInfo])
async def get_product_summary(db: Session, pagination: PaginationParams = Depends()):
    return await product_crud.get_product_summary(
        db, pagination.limit, pagination.offset
    )


@router.get("/filters/", response_model=list[str])
async def get_product_filters(db: Session):
    return await product_crud.get_product_attributes_list(db)


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_products(
    db: Session,
    admin: AdminUser,
    file: UploadFile = File(),
):
    return await product_crud.import_products(db, file)


@router.get("/popular/", response_model=list[ProductListRead])
@cache(expire=60)
async def get_popular_product(
    db: Session,
    redis: RedisDep,
    pagination: PaginationParams = Depends(),
):
    """
    Returns products sorted by unique views (popularity).
    Uses Redis Sorted Set for efficient ranking.
    """
    top_ids_str = await get_top_product_ids(
        redis, limit=pagination.limit, offset=pagination.offset
    )

    if not top_ids_str:
        return []

    product_ids = [uuid.UUID(pid) for pid in top_ids_str]

    products = await product_crud.get_products_by_ids(db, product_ids)

    return products
