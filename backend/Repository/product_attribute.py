import uuid
from typing import Any

from core.models.product import Product
from core.models.product_attribute import ProductAttribute
from core.schemas.product_attribute import (
    ProductAttributeCreate,
    ProductAttributeUpdate,
)
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _detect_data_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "numeric"
    if isinstance(value, str):
        return "text"
    return "text"


async def ensure_product_attributes_exist(
    session: AsyncSession, attributes: dict[str, Any]
) -> None:
    if not attributes:
        return

    keys = set()
    for key, value in attributes.items():
        key_str = str(key).strip()
        if key_str in {"Артикул", "article"}:
            continue
        keys.add((key_str, _detect_data_type(value)))

    if not keys:
        return

    existing_stmt = select(ProductAttribute.key)
    existing_result = await session.execute(existing_stmt)
    existing_keys = set(existing_result.scalars().all())

    new_attrs = []
    for key, data_type in keys:
        if key not in existing_keys:
            new_attrs.append(
                ProductAttribute(
                    key=key,
                    display_name=key,
                    data_type=data_type,
                    sort_order=0,
                    is_visible=True,
                )
            )

    if new_attrs:
        session.add_all(new_attrs)
        await session.commit()


async def get_product_attributes(
    session: AsyncSession,
    offset: int = 0,
    limit: int | None = None,
    visible_only: bool = False,
):
    stmt = select(ProductAttribute).order_by(
        ProductAttribute.sort_order, ProductAttribute.key
    )
    if visible_only:
        stmt = stmt.where(ProductAttribute.is_visible == True)
    if limit is not None:
        stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_product_attribute(
    session: AsyncSession, attribute_id: uuid.UUID
) -> ProductAttribute | None:
    return await session.get(ProductAttribute, attribute_id)


async def get_product_attribute_by_key(
    session: AsyncSession, key: str
) -> ProductAttribute | None:
    stmt = select(ProductAttribute).where(ProductAttribute.key == key)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_product_attribute(
    session: AsyncSession, data: ProductAttributeCreate
) -> ProductAttribute:
    attribute = ProductAttribute(**data.model_dump())
    session.add(attribute)
    await session.commit()
    await session.refresh(attribute)
    return attribute


async def update_product_attribute(
    session: AsyncSession,
    attribute: ProductAttribute,
    data: ProductAttributeUpdate,
) -> ProductAttribute:
    patch = data.model_dump(exclude_unset=True)
    for field, value in patch.items():
        setattr(attribute, field, value)
    await session.commit()
    await session.refresh(attribute)
    return attribute


async def delete_product_attribute(
    session: AsyncSession, attribute: ProductAttribute
) -> None:
    await session.delete(attribute)
    await session.commit()


async def delete_product_attributes(
    session: AsyncSession, ids: list[uuid.UUID]
) -> int:
    stmt = delete(ProductAttribute).where(ProductAttribute.id.in_(ids))
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount


async def delete_all_product_attributes(session: AsyncSession) -> int:
    count_stmt = select(func.count()).select_from(ProductAttribute)
    total = await session.scalar(count_stmt) or 0
    await session.execute(delete(ProductAttribute))
    await session.commit()
    return total


async def sync_product_attributes(session: AsyncSession) -> dict:
    stmt = select(func.jsonb_each(Product.attributes))
    result = await session.execute(stmt)

    all_keys: dict[str, str] = {}
    for row in result:
        key, value = row[0]
        key_str = str(key).strip()
        if key_str in {"Артикул", "article"}:
            continue
        if isinstance(value, bool):
            all_keys[key_str] = "boolean"
        elif isinstance(value, (int, float)):
            all_keys[key_str] = "numeric"
        elif isinstance(value, str):
            all_keys[key_str] = "text"

    existing_stmt = select(ProductAttribute)
    existing_result = await session.execute(existing_stmt)
    existing = {a.key: a for a in existing_result.scalars().all()}

    created = 0
    updated = 0
    deleted = 0

    for key, data_type in all_keys.items():
        if key in existing:
            attr = existing[key]
            changed = False
            if attr.data_type != data_type:
                attr.data_type = data_type
                changed = True
            if not attr.display_name:
                attr.display_name = key
                changed = True
            if changed:
                updated += 1
        else:
            new_attr = ProductAttribute(
                key=key,
                display_name=key,
                data_type=data_type,
                sort_order=len(all_keys),
                is_visible=True,
            )
            session.add(new_attr)
            created += 1

    keys_to_delete = [
        attr.id for key, attr in existing.items() if key not in all_keys
    ]
    if keys_to_delete:
        await session.execute(
            delete(ProductAttribute).where(
                ProductAttribute.id.in_(keys_to_delete)
            )
        )
        deleted = len(keys_to_delete)

    await session.commit()

    return {
        "created": created,
        "updated": updated,
        "deleted": deleted,
        "total": len(all_keys),
    }
