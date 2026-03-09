import uuid
from typing import Annotated

from core.config import settings
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.base import PaginationParams
from core.schemas.product import (
    ProductCreate,
    ProductRead,
    ProductSummaryInfo,
    ProductUpdate,
)
from crud import product as product_crud
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from utils.product import current_admin
from utils.analytics import track_product_view, get_product_views, get_multiple_product_views
from api.dependencies.redis import get_redis
from redis.asyncio import Redis

router = APIRouter(
    prefix=settings.api.v1.product,
    tags=["Products"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
AdminUser = Annotated[User, Depends(current_admin)]
RedisDep = Annotated[Redis, Depends(get_redis)]

def _get_client_identifier(request: Request) -> str:
    # Use user ID if authenticated, else IP address
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "id"):
        return str(user.id)
    
    # Try to get real IP from headers if behind proxy, else direct client IP
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/", response_model=list[ProductRead])
async def list_products(
    db: Session,
    redis: RedisDep,
    pagination: PaginationParams = Depends(),
):
    products = await product_crud.get_products(
        db, offset=pagination.offset, limit=pagination.limit
    )
    
    product_ids = [p.id for p in products]
    views = await get_multiple_product_views(redis, product_ids)
    
    # Attach views to the SQLAlchemy models (they will be converted by Pydantic)
    for product, view_count in zip(products, views):
        product.views = view_count
        
    return products


@router.get("/search", response_model=list[ProductRead])
async def search_products(
    db: Session,
    redis: RedisDep,
    pagination: PaginationParams = Depends(),
    q: str | None = Query(None, description="Search query"),
):
    products = await product_crud.search_products(
        db, q=q, offset=pagination.offset, limit=pagination.limit
    )
    
    product_ids = [p.id for p in products]
    views = await get_multiple_product_views(redis, product_ids)
    
    for product, view_count in zip(products, views):
        product.views = view_count
        
    return products


@router.post("/", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    db: Session,
    admin: AdminUser,
):
    product = await product_crud.create_product(db, data)
    product.views = 0
    return product


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
        
    # Track unique view
    identifier = _get_client_identifier(request)
    await track_product_view(redis, product_id, identifier)
    
    # Get total views
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
    # Safely delete from redis
    try:
        await redis.delete(f"product:{product_id}:unique_views")
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
        except Exception:
            pass


@router.get("/summary/", response_model=list[ProductSummaryInfo])
async def get_product_summary(db: Session, pagination: PaginationParams = Depends()):
    return await product_crud.get_product_summary(
        db, pagination.limit, pagination.offset
    )


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_products(
    db: Session,
    admin: AdminUser,
    file: UploadFile = File(),
):
    return await product_crud.import_products(db, file)
