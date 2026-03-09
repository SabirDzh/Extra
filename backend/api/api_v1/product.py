import uuid
from typing import Annotated

from core.config import settings
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.base import PaginationParams
from core.schemas.product import ProductCreate, ProductRead, ProductUpdate
from crud import product as product_crud
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from utils.product import current_admin

router = APIRouter(
    prefix=settings.api.v1.product,
    tags=["Products"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
AdminUser = Annotated[User, Depends(current_admin)]


@router.get("/", response_model=list[ProductRead])
async def list_products(
    db: Session,
    pagination: Annotated[PaginationParams, Query()],
):
    return await product_crud.get_products(
        db, offset=pagination.offset, limit=pagination.limit
    )


@router.get("/search", response_model=list[ProductRead])
async def search_products(
    db: Session,
    pagination: Annotated[PaginationParams, Query()],
    q: str | None = Query(None, description="Search query"),
):
    return await product_crud.search_products(
        db, q=q, offset=pagination.offset, limit=pagination.limit
    )


@router.post("/", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    db: Session,
    admin: AdminUser,
):
    return await product_crud.create_product(db, data)


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: uuid.UUID, db: Session):
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    return product


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID,
    data: ProductUpdate,
    db: Session,
    admin: AdminUser,
):
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    return await product_crud.update_product(db, product, data)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: uuid.UUID,
    db: Session,
    admin: AdminUser,
):
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    await product_crud.delete_product(db, product)


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_products(
    products_id: Annotated[list[uuid.UUID], Query()], db: Session, admin: AdminUser
):
    await product_crud.delete_products(db, products_id)
