import uuid
from typing import Any, List

from core.models.product import Product
from core.schemas.product import ProductCreate, ProductUpdate
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_products(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 20,
) -> List[Product]:
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
    for field, value in product_update.model_dump(exclude_unset=True).items():
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
) -> List[Product]:
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
