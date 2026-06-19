import uuid
from typing import List

from core.models.product import Product
from core.schemas.product import ProductCreate, ProductUpdate
from fastapi import UploadFile
from Repository import product as repo
from sqlalchemy.ext.asyncio import AsyncSession
from Repository.common import ensure_unique_field
from Services import product_attribute as attribute_crud


async def get_products(session: AsyncSession, **kwargs):
    return await repo.get_products(session, **kwargs)


async def get_product(session: AsyncSession, product_id: uuid.UUID) -> Product | None:
    return await repo.get_product(session, product_id)


async def create_product(session: AsyncSession, product_in: ProductCreate) -> Product:
    await ensure_unique_field(
        session,
        Product,
        "title",
        product_in.title,
        error_msg=f"Product with title '{product_in.title}' already exists",
    )
    product = await repo.create_product(session, product_in)
    if product_in.attributes:
        await attribute_crud.ensure_product_attributes_exist(
            session, product_in.attributes
        )
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
    updated = await repo.update_product(session, product, product_update)
    if product_update.attributes:
        await attribute_crud.ensure_product_attributes_exist(
            session, product_update.attributes
        )
    return updated


async def delete_product(session: AsyncSession, product: Product) -> None:
    await repo.delete_product(session, product)


async def get_products_by_ids(
    session: AsyncSession, product_ids: list[uuid.UUID]
) -> List[Product]:
    return await repo.get_products_by_ids(session, product_ids)


async def get_product_attributes_list(session: AsyncSession) -> list[str]:
    return await repo.get_product_attributes_list(session)


async def search_products(session: AsyncSession, **kwargs):
    return await repo.search_products(session, **kwargs)


async def delete_products(session: AsyncSession, products_id: list[uuid.UUID]):
    await repo.delete_products(session, products_id)


async def delete_all_products(session: AsyncSession) -> int:
    return await repo.delete_all_products(session)


async def get_product_summary(session: AsyncSession, limit: int, offset: int):
    return await repo.get_product_summary(session, limit, offset)


async def import_products(session: AsyncSession, file: UploadFile):
    return await repo.import_products(session, file)
