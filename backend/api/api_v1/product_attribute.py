import uuid
from typing import Annotated

from api.dependencies.authorization import current_admin
from core.authentication.fastapi_users import current_optional_user
from core.config import settings
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.product_attribute import (
    GroupedAttributeRead,
    ProductAttributeBulkDelete,
    ProductAttributeCreate,
    ProductAttributeRead,
    ProductAttributeUpdate,
)
from Domain.Enums.user_role import UserRole
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


@router.get(
    "/", response_model=list[ProductAttributeRead] | list[GroupedAttributeRead]
)
@router.get(
    "/filters", response_model=list[GroupedAttributeRead], include_in_schema=False
)
async def list_product_attributes(
    db: Session,
    offset: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=1000),
    visible_only: bool = Query(True),
    grouped: bool = Query(
        False,
        description="If true, returns attributes grouped into e-commerce range filters (min/max/values)",
    ),
    user: User | None = Depends(current_optional_user),
):
    if not visible_only:
        if not user or user.role != UserRole.admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can access hidden attributes",
            )
    if grouped:
        return await attribute_crud.get_grouped_product_attributes(
            db, visible_only=visible_only
        )
    return await attribute_crud.get_product_attributes(
        db, offset=offset, limit=limit, visible_only=visible_only
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
