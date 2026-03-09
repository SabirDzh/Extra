import uuid
from typing import List, Any
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.course import Course
from core.models.product import Product
from core.models.term import Term


async def global_search_entities(
    session: AsyncSession,
    q: str | None = None,
    limit_per_category: int = 5,
) -> dict:
    
    async def search_single_model(model):
        stmt = select(model)
        
        # Apply filters like is_published if available
        if hasattr(model, "is_published"):
            stmt = stmt.where(model.is_published == True)

        if not q:
            result = await session.execute(stmt.limit(limit_per_category))
            return result.scalars().all()

        if len(q) < 3:
            search_pattern = f"%{q}%"
            stmt = stmt.where(
                or_(
                    model.title.ilike(search_pattern),
                    model.description.ilike(search_pattern),
                )
            ).order_by(model.title.asc())
        else:
            stmt = stmt.where(
                or_(
                    model.title.bool_op("%")(q),
                    model.description.bool_op("%")(q),
                )
            ).order_by(
                func.similarity(model.title, q).desc(),
                func.similarity(model.description, q).desc(),
            )

        result = await session.execute(stmt.limit(limit_per_category))
        return result.scalars().all()

    courses = await search_single_model(Course)
    products = await search_single_model(Product)
    terms = await search_single_model(Term)

    return {
        "courses": courses,
        "products": products,
        "terms": terms,
    }
