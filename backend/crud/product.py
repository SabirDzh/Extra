import uuid
from typing import Sequence

from core.models.product import Product
from core.schemas.product import ProductCreate, ProductUpdate
from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_products(
    session: AsyncSession, offset: int = 0, limit: int = 10
) -> Sequence[Product]:
    stmt = select(Product).limit(limit).offset(offset)
    product = await session.scalars(stmt)
    return product.all()


async def get_product(
    session: AsyncSession,
    product_id: uuid.UUID,
) -> Product:
    product = await session.get(Product, product_id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


async def create_product(
    session: AsyncSession,
    productDTO: ProductCreate,
) -> Product:
    query = select(Product).where(Product.title == productDTO.title)
    existing_product = await session.execute(query)

    if existing_product.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this name already exists",
        )

    product = Product(**productDTO.model_dump())
    session.add(product)
    await session.commit()

    await session.refresh(product)
    return product


async def search_product(
    session: AsyncSession,
    search: str | None = None,
    limit: int = 10,
    similarity_threshold: float = 0.3,
) -> Sequence[Product]:
    if not search:
        return await get_products(session, limit=limit)

    similarity_score = func.similarity(Product.title, search)

    stmt = select(Product).where(
        or_(
            Product.title.op("%")(search),
            Product.search_product.op("@@")(
                func.websearch_to_tsquery("russian", search)
            ),
        )
    )

    stmt = stmt.order_by(
        desc(similarity_score),
        desc(
            func.ts_rank(
                Product.search_product,
                func.websearch_to_tsquery("russian", search),
            )
        ),
    )

    stmt = stmt.limit(limit)

    result = await session.execute(stmt)
    product = result.scalars().all()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


async def update_product(
    session: AsyncSession,
    product_id: uuid.UUID,
    productDTO: ProductUpdate,
) -> Product:
    product = await get_product(session, product_id)
    update_data = productDTO.model_dump(exclude_unset=True)

    for name, value in update_data.items():
        setattr(product, name, value)

    await session.commit()
    await session.refresh(product)

    return product


async def delete_product(
    session: AsyncSession,
    product_id: uuid.UUID,
) -> None:
    product = await get_product(session, product_id)
    await session.delete(product)
    await session.commit()
