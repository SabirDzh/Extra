import uuid
from typing import Annotated, Optional, Sequence

from core.models.product import Product
from core.schemas.product import (
    ProductCreate,
    ProductFilter,
    ProductFilterCountItemResponse,
    ProductFilterResponse,
    ProductUpdate,
)
from fastapi import HTTPException, Query, status
from sqlalchemy import Float, cast, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.filter import get_filtered


async def get_products(
    session: AsyncSession,
    offset: Annotated[int, Query(ge=0, gt=100)] = 0,
    limit: Annotated[int, Query(ge=0, gt=100)] = 10,
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
    search: Optional[str] = None,
    *,
    limit: Annotated[int, Query(ge=0, gt=0)] = 10,
    offset: Annotated[int, Query(ge=0, gt=0)] = 0,
    filters: Optional[ProductFilter] = None,
    similarity_threshold: float = 0.3,
) -> Sequence[Product]:
    if not search:
        return await get_products(session, limit=limit, offset=offset)

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

    # if filters:
    #     stmt = get_filtered(stmt, filters)

    stmt = stmt.limit(limit).offset(offset)

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


async def get_limits(session: AsyncSession) -> ProductFilterResponse:
    stmt = select(
        func.min(cast(Product.attributes["accuracy"].astext, Float)),
        func.max(cast(Product.attributes["accuracy"].astext, Float)),
        func.min(cast(Product.attributes["temp"].astext, Float)),
        func.max(cast(Product.attributes["temp"].astext, Float)),
    )
    result = await session.execute(stmt)
    min_acc, max_acc, min_tmp, max_tmp = result.one()
    return ProductFilterResponse(
        min_accuracy=min_acc or 0,
        max_accuracy=max_acc or 0,
        min_temp=min_tmp or 0,
        max_temp=max_tmp or 0,
    )


async def get_count_product_filter(
    session: AsyncSession,
) -> ProductFilterCountItemResponse:
    stmt = select(
        func.count(Product.attributes["accuracy"]),
        func.count(Product.attributes["temp"]),
        func.count(Product.attributes["equirement_type"]),
        func.count(Product.attributes["purpose"]),
        func.count(Product.attributes["industry"]),
        func.count(Product.attributes["signal_type"]),
        func.count(Product.attributes["ip_rating"]),
        func.count(Product.attributes["mounting"]),
    )
    result = await session.execute(stmt)
    acc, tmp, eq_type, pur, ind, sig_type, ip, moun = result.one()
    return ProductFilterCountItemResponse(
        accuracy=acc or 0,
        temp=tmp or 0,
        equipment_type=eq_type or 0,
        purpose=pur or 0,
        industry=ind or 0,
        signal_type=sig_type or 0,
        ip_rating=ip or 0,
        mounting=moun or 0,
    )
