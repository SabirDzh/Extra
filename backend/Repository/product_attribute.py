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
                    id=uuid.uuid4(),
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


def _normalize_unit(unit: str) -> str:
    u = unit.lower()
    if u in ("метр", "метра", "метров", "м"):
        return "метров"
    if u in ("бар", "бара", "баров"):
        return "бар"
    if u in ("миллиметр", "миллиметра", "миллиметров", "мм"):
        return "мм"
    if u in ("сантиметр", "сантиметра", "сантиметров", "см"):
        return "см"
    if u in ("килограмм", "килограмма", "килограммов", "кг"):
        return "кг"
    if u in ("ватт", "ватта", "ваттов", "вт"):
        return "Вт"
    if u in ("киловатт", "киловатта", "киловаттов", "квт"):
        return "кВт"
    if u in ("литр", "литра", "литров", "л"):
        return "л"
    return unit


async def get_grouped_product_attributes(
    session: AsyncSession,
    visible_only: bool = False,
) -> list[dict]:
    import re

    attributes = await get_product_attributes(
        session, offset=0, limit=None, visible_only=visible_only
    )

    pattern = re.compile(
        r"^(?P<base>.*?\D)\s*(?P<val>\d+(?:[.,]\d+)?)\s*(?P<unit>[A-Za-zА-Яа-я%°/]+)$"
    )

    grouped: dict[str, dict] = {}
    standalone: list[dict] = []

    for attr in attributes:
        key = attr.key.strip()
        match = pattern.match(key)
        if match:
            base_title = match.group("base").strip()
            raw_unit = match.group("unit").strip()
            norm_unit = _normalize_unit(raw_unit)
            val_str = match.group("val").replace(",", ".")
            try:
                num_val = float(val_str)
            except ValueError:
                num_val = None

            if num_val is not None and base_title:
                group_key = base_title.lower()
                if group_key not in grouped:
                    grouped[group_key] = {
                        "title": base_title,
                        "unit": norm_unit,
                        "filter_type": "range",
                        "min_value": num_val,
                        "max_value": num_val,
                        "values": set([num_val]),
                        "attribute_ids": [attr.id],
                        "original_keys": [key],
                        "sort_order": attr.sort_order,
                    }
                else:
                    item = grouped[group_key]
                    item["values"].add(num_val)
                    item["min_value"] = min(item["min_value"], num_val)
                    item["max_value"] = max(item["max_value"], num_val)
                    item["attribute_ids"].append(attr.id)
                    item["original_keys"].append(key)
                continue

        # Non-range attributes: return in standard ProductAttributeRead format
        standalone.append(
            {
                "id": attr.id,
                "key": attr.key,
                "display_name": attr.display_name or attr.key,
                "data_type": attr.data_type,
                "sort_order": attr.sort_order,
                "is_visible": attr.is_visible,
                "created_at": attr.created_at,
                "updated_at": attr.updated_at,
            }
        )

    result = []
    for grp in grouped.values():
        grp["values"] = sorted(list(grp["values"]))
        result.append(grp)

    result.extend(standalone)
    return sorted(
        result,
        key=lambda x: (x.get("sort_order", 0), x.get("title") or x.get("key") or ""),
    )


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
    all_keys: dict[str, str] = {}
    if session.bind and session.bind.dialect.name == "sqlite":
        stmt = select(Product.attributes)
        res = await session.execute(stmt)
        for (attrs,) in res:
            if not attrs or not isinstance(attrs, dict):
                continue
            for key, value in attrs.items():
                key_str = str(key).strip()
                if key_str in {"Артикул", "article"}:
                    continue
                if isinstance(value, bool):
                    all_keys[key_str] = "boolean"
                elif isinstance(value, (int, float)):
                    all_keys[key_str] = "numeric"
                elif isinstance(value, str):
                    all_keys[key_str] = "text"
    else:
        stmt = select(func.jsonb_each(Product.attributes))
        result = await session.execute(stmt)
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
                id=uuid.uuid4(),
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
