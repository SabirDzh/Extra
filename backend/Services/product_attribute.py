import uuid
from typing import Any

from core.models.product_attribute import ProductAttribute
from core.schemas.product_attribute import (
    ProductAttributeCreate,
    ProductAttributeUpdate,
)
from Repository import product_attribute as repo
from sqlalchemy.ext.asyncio import AsyncSession


async def get_product_attributes(
    session: AsyncSession,
    offset: int = 0,
    limit: int | None = None,
    visible_only: bool = False,
):
    return await repo.get_product_attributes(session, offset, limit, visible_only)


async def get_product_attribute(
    session: AsyncSession, attribute_id: uuid.UUID
) -> ProductAttribute | None:
    return await repo.get_product_attribute(session, attribute_id)


async def get_product_attribute_by_key(
    session: AsyncSession, key: str
) -> ProductAttribute | None:
    return await repo.get_product_attribute_by_key(session, key)


async def create_product_attribute(
    session: AsyncSession, data: ProductAttributeCreate
) -> ProductAttribute:
    existing = await repo.get_product_attribute_by_key(session, data.key)
    if existing:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Attribute with key '{data.key}' already exists",
        )
    return await repo.create_product_attribute(session, data)


async def update_product_attribute(
    session: AsyncSession,
    attribute: ProductAttribute,
    data: ProductAttributeUpdate,
) -> ProductAttribute:
    return await repo.update_product_attribute(session, attribute, data)


async def delete_product_attribute(
    session: AsyncSession, attribute: ProductAttribute
) -> None:
    await repo.delete_product_attribute(session, attribute)


async def delete_product_attributes(
    session: AsyncSession, ids: list[uuid.UUID]
) -> int:
    return await repo.delete_product_attributes(session, ids)


async def delete_all_product_attributes(session: AsyncSession) -> int:
    return await repo.delete_all_product_attributes(session)


async def sync_product_attributes(session: AsyncSession) -> dict:
    return await repo.sync_product_attributes(session)


async def ensure_product_attributes_exist(
    session: AsyncSession, attributes: dict[str, Any]
) -> None:
    await repo.ensure_product_attributes_exist(session, attributes)
