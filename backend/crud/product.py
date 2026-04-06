import io
import json
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
from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.db import ensure_unique_field


async def get_products(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 20,
    sort_by: str = "title",
    order: str = "asc",
    features: list[str] | None = None,
):
    stmt = select(Product)
    if features:
        for feature in features:
            stmt = stmt.where(Product.attributes[feature].as_boolean())

    if sort_by == "title":
        sort_column = Product.title
    elif sort_by == "created_at":
        sort_column = Product.created_at
    elif sort_by == "article":
        sort_column = Product.attributes["Артикул"].as_string().cast(sa.BigInteger)
    else:
        sort_column = Product.title

    if order == "desc":
        stmt = stmt.order_by(sort_column.desc())
    else:
        stmt = stmt.order_by(sort_column.asc())

    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_product(session: AsyncSession, product_id: uuid.UUID) -> Product | None:
    return await session.get(Product, product_id)


async def create_product(session: AsyncSession, product_in: ProductCreate) -> Product:
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
    session: AsyncSession, product: Product, product_update: ProductUpdate
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
    # Получаем все пары ключ-значение из атрибутов всех товаров
    stmt = select(func.jsonb_each(Product.attributes))
    result = await session.execute(stmt)

    boolean_keys = set()
    for row in result:
        key, value = row[0]  # row[0] is a tuple (key, value) from jsonb_each
        # Проверяем, является ли значение булевым
        if isinstance(value, bool):
            boolean_keys.add(key)

    # Исключаем системные или ненужные поля, если они попали в булевы
    filtered_keys = [k for k in boolean_keys if k != "Артикул"]
    return sorted(filtered_keys)


async def search_products(
    session: AsyncSession,
    q: str | None = None,
    offset: int = 0,
    limit: int = 20,
    sort_by: str = "title",
    order: str = "asc",
    features: list[str] | None = None,
):
    stmt = select(Product)
    if q and len(q) >= 2:
        is_sqlite = session.bind.url.drivername.startswith("sqlite")
        if is_sqlite:
            search_pattern = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Product.title.ilike(search_pattern),
                    Product.description.ilike(search_pattern),
                )
            )
        else:
            ts_query = func.websearch_to_tsquery("russian", q)
            stmt = stmt.where(
                or_(
                    Product.search_product.bool_op("@@")(ts_query),
                    Product.title.bool_op("%")(q),
                    Product.description.bool_op("%")(q),
                )
            )
            if sort_by == "title" and order == "asc":
                relevance = (
                    func.ts_rank(Product.search_product, ts_query)
                    + func.similarity(Product.title, q) * 2
                    + func.similarity(Product.description, q) * 0.5
                )
                stmt = stmt.order_by(relevance.desc())
    elif q:
        search_pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Product.title.ilike(search_pattern),
                Product.description.ilike(search_pattern),
            )
        )

    if features:
        for feature in features:
            stmt = stmt.where(Product.attributes[feature].as_boolean() == True)

    if not q or sort_by != "title" or order != "asc":
        if sort_by == "title":
            sort_column = Product.title
        elif sort_by == "created_at":
            sort_column = Product.created_at
        elif sort_by == "article":
            sort_column = Product.attributes["Артикул"].as_string().cast(sa.BigInteger)
        else:
            sort_column = Product.title

        if order == "desc":
            stmt = stmt.order_by(sort_column.desc())
        else:
            stmt = stmt.order_by(sort_column.asc())

    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


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

    # Iterate through rows where data exists
    # row 1 is header, data starts from row 2
    for i in range(2, df_len + 2):
        cell_address = f"{target_col_letter}{i}"

        # Check if cell has an image in the loader's internal storage
        # SheetImageLoader stores images in a dictionary-like structure
        try:
            # We try to get the image. If it doesn't exist, it usually raises a ValueError
            image = image_loader.get(cell_address)

            filename = f"{uuid.uuid4()}.webp"
            filepath = img_dir / filename

            # Convert and save as WebP
            if image.mode in ("P", "CMYK"):
                image = image.convert("RGB")
            image.save(filepath, "WEBP", quality=85, optimize=True)

            # pandas_idx = excel_row - 2
            row_images[i - 2] = f"/media/product_img/{filename}"
        except (ValueError, KeyError):
            # No image in this cell
            continue
        except Exception as e:
            print(f"Error loading image at {cell_address}: {e}")
            continue

    return row_images


def parse_product_excel_file(contents: bytes) -> list[dict]:
    # 1. First, read headers to find the 'Изображение' column
    df_tmp = pd.read_excel(io.BytesIO(contents), nrows=0)

    image_col_idx = -1
    for i, col in enumerate(df_tmp.columns):
        if str(col).strip() in ["Изображение", "image_url"]:
            image_col_idx = i
            break

    # 2. Convert index to Excel column letter (0 -> A, 1 -> B, 2 -> C...)
    if image_col_idx != -1:
        # Simple conversion for A-Z columns
        target_col_letter = chr(65 + image_col_idx)
    else:
        target_col_letter = None

    # 3. Read data
    df = pd.read_excel(io.BytesIO(contents))
    df = df.fillna("")

    # 4. Extract images if column found
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

        # Add embedded image if found
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
                        val_str = str(val).strip()
                        if val_str.startswith("[") and val_str.endswith("]"):
                            try:
                                txt_imgs = json.loads(val_str)
                                product_dict["image_url"].extend(txt_imgs)
                            except Exception:
                                product_dict["image_url"].append(val_str)
                        else:
                            product_dict["image_url"].append(val_str)
                else:
                    product_dict[target_field] = str(val).strip()
            else:
                clean_col = " ".join(col_str.split())
                if val == "Есть":
                    attrs[clean_col] = True
                elif val == "Нет":
                    attrs[clean_col] = False
                elif val != "":
                    try:
                        if isinstance(val, (int, float)):
                            attrs[clean_col] = val
                        else:
                            val_str = str(val).strip()
                            if val_str.isdigit():
                                attrs[clean_col] = int(val_str)
                            else:
                                attrs[clean_col] = val_str
                    except Exception:
                        attrs[clean_col] = val

        product_dict["attributes"] = attrs
        if product_dict["title"]:
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
