from core.models.product import Product
from core.schemas.product import ProductFilter
from sqlalchemy import Float, cast, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncSession


async def get_filtered(
    session: AsyncSession,
    filters: ProductFilter,
):
    stmt = select(Product)

    if filters.equipment_type:
        stmt = stmt.where(
            Product.attributes["equipment_type"].has_any(array(filters.equipment_type))
        )
    if filters.industry:
        stmt = stmt.where(Product.attributes["industry"].has_any(array(filters.industry)))
    if filters.ip_rating:
        stmt = stmt.where(Product.attributes["ip_rating"].astext == filters.ip_rating)
    if filters.purpose:
        stmt = stmt.where(Product.attributes["purpose"].has_any(array(filters.purpose)))
    if filters.signal_type:
        stmt = stmt.where(
            Product.attributes["signal_type"].has_any(array(filters.signal_type))
        )
    if filters.mounting:
        stmt = stmt.where(Product.attributes["mounting"].has_any(array(filters.mounting)))
    if filters.min_accuracy is not None:
        stmt = stmt.where(
            cast(Product.attributes["accuracy"].astext, Float) >= filters.min_accuracy
        )
    if filters.max_accuracy is not None:
        stmt = stmt.where(
            cast(Product.attributes["accuracy"].astext, Float) <= filters.max_accuracy
        )
    if filters.min_temp is not None:
        stmt = stmt.where(
            cast(Product.attributes["temp"].astext, Float) >= filters.min_temp
        )
    if filters.max_temp is not None:
        stmt = stmt.where(
            cast(Product.attributes["temp"].astext, Float) <= filters.max_temp
        )

    result = await session.execute(stmt)
    return result.scalars().all()
