import csv
import io
import json
import uuid
from typing import Any, List

import pandas as pd
from core.models.product import Product
from core.schemas.product import ProductCreate, ProductUpdate
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.db import ensure_unique_field


async def get_products(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 20,
):
    stmt = select(Product).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_product(
    session: AsyncSession,
    product_id: uuid.UUID,
) -> Product | None:
    return await session.get(Product, product_id)


async def create_product(
    session: AsyncSession,
    product_in: ProductCreate,
) -> Product:
    # Check for duplicate title using utility
    await ensure_unique_field(
        session,
        Product,
        "title",
        product_in.title,
        error_msg=f"Product with title '{product_in.title}' already exists",
    )

    product = Product(**product_in.model_dump())
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


async def update_product(
    session: AsyncSession,
    product: Product,
    product_update: ProductUpdate,
) -> Product:
    patch = product_update.model_dump(exclude_unset=True)

    if "title" in patch and patch["title"]:
        await ensure_unique_field(
            session,
            Product,
            "title",
            patch["title"],
            exclude_id=product.id,
            error_msg=f"Product with title '{patch['title']}' already exists",
        )

    for field, value in patch.items():
        setattr(product, field, value)

    await session.commit()
    await session.refresh(product)
    return product


async def delete_product(
    session: AsyncSession,
    product: Product,
) -> None:
    await session.delete(product)
    await session.commit()


async def search_products(
    session: AsyncSession,
    q: str | None = None,
    offset: int = 0,
    limit: int = 20,
):
    stmt = select(Product)
    if q:
        if len(q) < 3:
            search_pattern = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Product.title.ilike(search_pattern),
                    Product.description.ilike(search_pattern),
                )
            ).order_by(Product.title.asc())
        else:
            stmt = stmt.where(
                or_(
                    Product.title.bool_op("%")(q),
                    Product.description.bool_op("%")(q),
                )
            ).order_by(
                func.similarity(Product.title, q).desc(),
                func.similarity(Product.description, q).desc(),
            )

    result = await session.execute(stmt.offset(offset).limit(limit))
    return result.scalars().all()


async def delete_products(session: AsyncSession, products_id: list[uuid.UUID]):
    stmt = delete(Product).where(Product.id.in_(products_id))
    await session.execute(stmt)
    await session.commit()


async def get_product_summary(
    session: AsyncSession,
    limit: int,
    offset: int,
):
    stmt = (
        select(Product.id, Product.title, Product.description)
        .limit(limit)
        .offset(offset)
        .order_by(Product.created_at)
    )
    return (await session.execute(stmt)).mappings().all()


def check_format(filename: str) -> str:
    filename = filename.lower()
    if not filename.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Разрешены только файлы форматов CSV и Excel (.xlsx, .xls)",
        )
    return filename


def parse_product_csv_file(contents: bytes) -> list[dict]:
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл CSV должен быть в кодировке UTF-8",
        )

    products_data = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        title = row.get("title", "")
        description = row.get("description", "")

        attributes = {}
        if "attributes" in row and row["attributes"].strip():
            try:
                attributes = json.loads(row["attributes"])
            except json.JSONDecodeError:
                pass

        image_url = []
        if "image_url" in row and row["image_url"].strip():
            try:
                image_url = json.loads(row["image_url"])
            except json.JSONDecodeError:
                image_url = [row["image_url"].strip()]

        schema_connect = row.get("schema_connect", "")
        documentation = row.get("documentation", "")

        if title and title.strip():
            products_data.append(
                {
                    "title": title.strip(),
                    "description": description.strip() if description else "",
                    "attributes": attributes,
                    "image_url": image_url,
                    "schema_connect": (
                        schema_connect.strip() if schema_connect else None
                    ),
                    "documentation": documentation.strip() if documentation else None,
                }
            )
    return products_data


def parse_product_excel_file(contents: bytes) -> list[dict]:
    df = pd.read_excel(io.BytesIO(contents))

    if "title" not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="В файле Excel отсутствует обязательная колонка 'title'",
        )

    df = df.fillna("")
    products_data = []

    for index, row in df.iterrows():
        title = str(row.get("title", "")).strip()
        description = str(row.get("description", "")).strip()

        attributes_raw = str(row.get("attributes", "")).strip()
        attributes = {}
        if attributes_raw:
            try:
                attributes = json.loads(attributes_raw)
            except json.JSONDecodeError:
                pass

        image_url_raw = str(row.get("image_url", "")).strip()
        image_url = []
        if image_url_raw:
            try:
                image_url = json.loads(image_url_raw)
            except json.JSONDecodeError:
                image_url = [image_url_raw]

        schema_connect = str(row.get("schema_connect", "")).strip()
        documentation = str(row.get("documentation", "")).strip()

        if title:
            products_data.append(
                {
                    "title": title,
                    "description": description,
                    "attributes": attributes,
                    "image_url": image_url,
                    "schema_connect": schema_connect if schema_connect else None,
                    "documentation": documentation if documentation else None,
                }
            )

    return products_data


async def import_products(session: AsyncSession, file: UploadFile):
    filename = check_format(file.filename)

    try:
        contents = await file.read()

        if filename.endswith(".csv"):
            products_data = parse_product_csv_file(contents)
        else:
            products_data = parse_product_excel_file(contents)

        if not products_data:
            return {"message": "Файл пуст или не содержит валидных данных для импорта"}

        # Exclude duplicates
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
            "msg": f"Успешно импортировано приборов: {len(new_products)}. Пропущено дубликатов: {len(products_data) - len(new_products)}.",
            "status": "OK",
        }

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при импорте: {str(e)}",
        )
