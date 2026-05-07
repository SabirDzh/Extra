import io
import json
import re
import uuid
from typing import List

import openpyxl
import pandas as pd
import sqlalchemy as sa
from core.config import BASE_DIR, settings
from core.models.product import Product
from core.schemas.product import ProductCreate, ProductUpdate
from fastapi import HTTPException, UploadFile, status
from openpyxl_image_loader import SheetImageLoader
from PIL import Image as PILImage
from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only
from Repository.common import sanitize_import_text
from Repository.search_engine import (
    MAX_SEARCH_CANDIDATES,
    SearchIn,
    SearchSort,
    attributes_to_search_text,
    filter_and_rank_items,
    paginate_items,
    sort_items,
)


def _normalize_feature_key(key: str) -> str:
    pattern = re.compile(
        r"^(?P<base>.*?\D)\s*(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>[A-Za-zА-Яа-я%°/]+)$"
    )
    key_str = str(key).strip()
    match = pattern.match(key_str)
    if not match:
        return key_str
    base = match.group("base").strip()
    return base or key_str


def _has_feature(attributes: dict | None, feature: str) -> bool:
    if not attributes:
        return False
    feature_norm = _normalize_feature_key(feature)
    for key, value in attributes.items():
        if value is not True:
            continue
        key_str = str(key).strip()
        if key_str == feature or _normalize_feature_key(key_str) == feature_norm:
            return True
    return False


def _apply_features_filter(
    products: list[Product], features: list[str] | None
) -> list[Product]:
    if not features:
        return products
    filtered: list[Product] = []
    for product in products:
        attrs = product.attributes if isinstance(product.attributes, dict) else {}
        if all(_has_feature(attrs, feature) for feature in features):
            filtered.append(product)
    return filtered


async def get_products(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 20,
    sort_by: str = "title",
    order: str = "asc",
    features: list[str] | None = None,
):
    stmt = select(Product).options(
        load_only(
            Product.id,
            Product.title,
            Product.image_url,
            Product.created_at,
            Product.description,
            Product.attributes,
        )
    )
    result = await session.execute(stmt)
    products = list(result.scalars().all())
    products = _apply_features_filter(products, features)

    reverse = order == "desc"
    if sort_by == "created_at":
        products.sort(
            key=lambda item: (item.created_at is None, item.created_at),
            reverse=reverse,
        )
    elif sort_by == "description":
        products.sort(key=lambda item: (item.description or "").lower(), reverse=reverse)
    else:
        products.sort(key=lambda item: (item.title or "").lower(), reverse=reverse)

    return paginate_items(products, offset=offset, limit=limit)


async def get_product(session: AsyncSession, product_id: uuid.UUID) -> Product | None:
    return await session.get(Product, product_id)


async def create_product(session: AsyncSession, product_in: ProductCreate) -> Product:
    product = Product(**product_in.model_dump())
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


async def update_product(
    session: AsyncSession, product: Product, product_update: ProductUpdate
) -> Product:
    patch = product_update.model_dump(exclude_unset=True)
    for field, value in patch.items():
        setattr(product, field, value)
    await session.commit()
    await session.refresh(product)
    return product


async def delete_product(session: AsyncSession, product: Product) -> None:
    await session.delete(product)
    await session.commit()


async def get_products_by_ids(
    session: AsyncSession, product_ids: list[uuid.UUID]
) -> List[Product]:
    if not product_ids:
        return []
    stmt = select(Product).where(Product.id.in_(product_ids))
    result = await session.execute(stmt)
    products = result.scalars().all()
    product_map = {p.id: p for p in products}
    return [product_map[pid] for pid in product_ids if pid in product_map]


async def get_product_attributes_list(session: AsyncSession) -> list[str]:
    stmt = select(func.jsonb_each(Product.attributes))
    result = await session.execute(stmt)

    boolean_keys = set()
    for row in result:
        key, value = row[0]
        if isinstance(value, bool):
            if not value:
                continue
            key_str = str(key).strip()
            boolean_keys.add(_normalize_feature_key(key_str))

    filtered_keys = [k for k in boolean_keys if k != "Артикул"]
    return sorted(filtered_keys)


async def search_products(
    session: AsyncSession,
    q: str | None = None,
    offset: int = 0,
    limit: int = 20,
    sort: SearchSort = "alphabet_asc",
    search_in: SearchIn = "all",
    features: list[str] | None = None,
):
    stmt = select(Product).options(
        load_only(
            Product.id,
            Product.title,
            Product.image_url,
            Product.created_at,
            Product.description,
            Product.attributes,
        )
    )

    stmt = stmt.limit(MAX_SEARCH_CANDIDATES)
    result = await session.execute(stmt)
    products = list(result.scalars().all())
    products = _apply_features_filter(products, features)
    ranked = filter_and_rank_items(
        products,
        q=q,
        search_in=search_in,
        title_getter=lambda item: item.title,
        description_getter=lambda item: item.description,
        filter_text_getter=lambda item: attributes_to_search_text(item.attributes),
    )
    sorted_items = sort_items(
        ranked,
        sort=sort,
        title_getter=lambda item: item.title,
        date_getter=lambda item: item.created_at,
    )
    return paginate_items(sorted_items, offset=offset, limit=limit)


async def delete_products(session: AsyncSession, products_id: list[uuid.UUID]):
    stmt = delete(Product).where(Product.id.in_(products_id))
    await session.execute(stmt)
    await session.commit()


async def delete_all_products(session: AsyncSession) -> int:
    count_stmt = select(func.count()).select_from(Product)
    total = await session.scalar(count_stmt) or 0
    await session.execute(delete(Product))
    await session.commit()
    return total


async def get_product_summary(session: AsyncSession, limit: int, offset: int):
    stmt = (
        select(Product.id, Product.title, Product.description, Product.image_url)
        .limit(limit)
        .offset(offset)
        .order_by(Product.created_at)
    )
    return (await session.execute(stmt)).mappings().all()


def check_format(filename: str) -> str:
    filename = filename.lower()
    if not filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Разрешены только файлы форматов CSV и Excel (.xlsx, .xls)",
        )
    return filename


def extract_images_using_loader(
    contents: bytes, target_col_letter: str, df_len: int
) -> dict[int, str]:
    """
    Extracts images from a specific column using openpyxl-image-loader.
    Returns mapping: pandas_row_index -> relative_url.
    """
    wb = openpyxl.load_workbook(io.BytesIO(contents))
    ws = wb.active
    image_loader = SheetImageLoader(ws)

    img_dir = BASE_DIR / "media" / "product_img"
    img_dir.mkdir(parents=True, exist_ok=True)

    row_images = {}

    for i in range(2, df_len + 2):
        cell_address = f"{target_col_letter}{i}"

        try:
            image = image_loader.get(cell_address)

            filename = f"{uuid.uuid4()}.webp"
            filepath = img_dir / filename

            # Convert and save as WebP
            if image.mode in ("P", "CMYK"):
                image = image.convert("RGB")
            image.save(filepath, "WEBP", quality=85, optimize=True)

            row_images[i - 2] = f"/media/product_img/{filename}"
        except (ValueError, KeyError):
            continue
        except Exception as e:
            print(f"Error loading image at {cell_address}: {e}")
            continue

    return row_images


def parse_product_excel_file(contents: bytes) -> list[dict]:
    df_tmp = pd.read_excel(io.BytesIO(contents), nrows=0)

    image_col_idx = -1
    for i, col in enumerate(df_tmp.columns):
        if str(col).strip() in ["Изображение", "image_url"]:
            image_col_idx = i
            break

    if image_col_idx != -1:
        target_col_letter = chr(65 + image_col_idx)
    else:
        target_col_letter = None

    df = pd.read_excel(io.BytesIO(contents))
    df = df.fillna("")

    row_to_image = {}
    if target_col_letter:
        row_to_image = extract_images_using_loader(contents, target_col_letter, len(df))

    mapping = {
        "Название": "title",
        "title": "title",
        "Описание": "description",
        "description": "description",
        "Изображение": "image_url",
        "image_url": "image_url",
        "Ссылка": "documentation",
        "documentation": "documentation",
        "Схема подключения": "schema_connect",
        "schema_connect": "schema_connect",
    }

    products_data = []
    for index, row in df.iterrows():
        product_dict = {
            "title": "",
            "description": "",
            "attributes": {},
            "image_url": [],
            "schema_connect": None,
            "documentation": None,
        }

        if index in row_to_image:
            product_dict["image_url"].append(row_to_image[index])

        attrs = {}
        for col in df.columns:
            val = row[col]
            col_str = str(col).strip()
            if col_str.startswith("Unnamed:"):
                continue

            if col_str in mapping:
                target_field = mapping[col_str]
                if target_field == "image_url":
                    if val:  # Handle text links
                        val_str = sanitize_import_text(val, normalize_slashes=True)
                        if val_str.startswith("[") and val_str.endswith("]"):
                            try:
                                txt_imgs = json.loads(val_str)
                                product_dict["image_url"].extend(txt_imgs)
                            except Exception:
                                product_dict["image_url"].append(val_str)
                        else:
                            product_dict["image_url"].append(val_str)
                else:
                    normalize_slashes = target_field in {"schema_connect", "documentation"}
                    product_dict[target_field] = sanitize_import_text(
                        val,
                        normalize_slashes=normalize_slashes,
                    )
            else:
                clean_col = sanitize_import_text(col_str)
                if val == "Есть":
                    attrs[clean_col] = True
                elif val == "Нет":
                    attrs[clean_col] = False
                elif val != "":
                    try:
                        if isinstance(val, (int, float)):
                            attrs[clean_col] = val
                        else:
                            val_str = sanitize_import_text(val)
                            if val_str.isdigit():
                                attrs[clean_col] = int(val_str)
                            else:
                                attrs[clean_col] = val_str
                    except Exception:
                        attrs[clean_col] = val

        product_dict["attributes"] = attrs
        if product_dict["title"]:
            product_dict["title"] = sanitize_import_text(product_dict["title"])
            product_dict["description"] = sanitize_import_text(product_dict["description"])
            products_data.append(product_dict)

    return products_data


async def import_products(session: AsyncSession, file: UploadFile):
    filename = check_format(file.filename)
    try:
        contents = await file.read()
        products_data = parse_product_excel_file(contents)

        if not products_data:
            return {"message": "Файл пуст или не содержит валидных данных"}

        incoming_titles = [p["title"] for p in products_data]
        stmt = select(Product.title).where(Product.title.in_(incoming_titles))
        existing_result = await session.execute(stmt)
        existing_titles = set(existing_result.scalars().all())

        new_products = [p for p in products_data if p["title"] not in existing_titles]
        if not new_products:
            return {
                "message": f"Найдено {len(products_data)} записей, но все они уже существуют."
            }

        stmt_insert = insert(Product).values(new_products)
        await session.execute(stmt_insert)
        await session.commit()

        return {
            "msg": f"Успешно импортировано приборов: {len(new_products)}. Изображений сохранено (WebP): {sum(len(p['image_url']) for p in new_products)}.",
            "status": "OK",
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при импорте: {str(e)}",
        )
