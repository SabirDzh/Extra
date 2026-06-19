import uuid
from typing import Annotated

from api.dependencies.authorization import current_admin
from core.config import settings
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.product_attribute import (
    ProductAttributeBulkDelete,
    ProductAttributeCreate,
    ProductAttributeRead,
    ProductAttributeUpdate,
)
from Services import product_attribute as attribute_crud
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix=settings.api.v1.product_attributes,
    tags=["Product Attributes"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
AdminUser = Annotated[User, Depends(current_admin)]


@router.get("/", response_model=list[ProductAttributeRead])
async def list_product_attributes(
    db: Session,
    offset: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=1000),
):
    return await attribute_crud.get_product_attributes(
        db, offset=offset, limit=limit
    )


@router.get("/active", response_model=list[ProductAttributeRead])
async def list_active_product_attributes(db: Session):
    return await attribute_crud.get_product_attributes(
        db, visible_only=True
    )


@router.get("/{attribute_id}", response_model=ProductAttributeRead)
async def get_product_attribute(
    db: Session,
    attribute_id: Annotated[uuid.UUID, Path()],
):
    attribute = await attribute_crud.get_product_attribute(db, attribute_id)
    if not attribute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product attribute not found",
        )
    return attribute


@router.post(
    "/",
    response_model=ProductAttributeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_product_attribute(
    db: Session,
    data: ProductAttributeCreate,
    admin: AdminUser,
):
    return await attribute_crud.create_product_attribute(db, data)


@router.patch("/{attribute_id}", response_model=ProductAttributeRead)
async def update_product_attribute(
    db: Session,
    attribute_id: uuid.UUID,
    data: ProductAttributeUpdate,
    admin: AdminUser,
):
    attribute = await attribute_crud.get_product_attribute(db, attribute_id)
    if not attribute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product attribute not found",
        )
    return await attribute_crud.update_product_attribute(db, attribute, data)


@router.delete("/{attribute_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_attribute(
    db: Session,
    attribute_id: uuid.UUID,
    admin: AdminUser,
):
    attribute = await attribute_crud.get_product_attribute(db, attribute_id)
    if not attribute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product attribute not found",
        )
    await attribute_crud.delete_product_attribute(db, attribute)


@router.delete("/bulk", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_attributes_bulk(
    db: Session,
    data: ProductAttributeBulkDelete,
    admin: AdminUser,
):
    await attribute_crud.delete_product_attributes(db, data.ids)


@router.delete("/clear", status_code=status.HTTP_200_OK)
async def clear_all_product_attributes(
    db: Session,
    admin: AdminUser,
):
    count = await attribute_crud.delete_all_product_attributes(db)
    return {"msg": f"Удалено атрибутов: {count}", "status": "OK"}


@router.post("/sync", status_code=status.HTTP_200_OK)
async def sync_product_attributes(
    db: Session,
    admin: AdminUser,
):
    result = await attribute_crud.sync_product_attributes(db)
    return {
        "msg": "Синхронизация завершена",
        "created": result["created"],
        "updated": result["updated"],
        "deleted": result["deleted"],
        "total": result["total"],
    }
