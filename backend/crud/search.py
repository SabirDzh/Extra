import uuid
from typing import List, Any
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.course import Course
from core.models.product import Product
from core.models.term import Term
from core.models.error import Error
from core.models.faq import FAQ


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

        title_field = getattr(model, "title", getattr(model, "question", None))
        desc_field = getattr(model, "description", getattr(model, "answer", None))

        if not q or not title_field or not desc_field:
            result = await session.execute(stmt.limit(limit_per_category))
            return result.scalars().all()

        if len(q) < 2:
            search_pattern = f"%{q}%"
            stmt = stmt.where(
                or_(
                    title_field.ilike(search_pattern),
                    desc_field.ilike(search_pattern),
                )
            ).order_by(title_field.asc())
        else:
            relevance = (
                func.similarity(title_field, q) * 2
                + func.similarity(desc_field, q) * 0.5
            )
            search_pattern = f"%{q}%"
            stmt = stmt.where(
                or_(
                    title_field.bool_op("%")(q),
                    desc_field.bool_op("%")(q),
                    title_field.ilike(search_pattern),
                    desc_field.ilike(search_pattern),
                )
            ).order_by(relevance.desc())

        result = await session.execute(stmt.limit(limit_per_category))
        return result.scalars().all()

    courses = await search_single_model(Course)
    products = await search_single_model(Product)
    terms = await search_single_model(Term)
    errors = await search_single_model(Error)
    faqs = await search_single_model(FAQ)

    return {
        "courses": courses,
        "products": products,
        "terms": terms,
        "errors": errors,
        "faqs": faqs,
    }
