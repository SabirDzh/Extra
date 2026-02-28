from typing import Annotated

from core.config import settings
from core.models.course import Course
from core.models.db_helper import db_helper
from core.models.product import Product

# from core.models.faq import FAQ  # Раскомментируйте, когда добавите модель FAQ
from core.schemas.search import GlobalSearchResult, SearchType
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix=settings.api.v1.search, tags=["Global Search"])
Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]


@router.get("/all", response_model=list[GlobalSearchResult])
async def global_search(
    db: Session,
    query: Annotated[str, Query(description="Search query", min_length=2)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    results = []

    product_similarity = func.similarity(Product.title, query).label("relevance")

    stmt_products = (
        select(Product, product_similarity)
        .where(
            or_(
                Product.title.op("%")(query),
                Product.search_product.op("@@")(
                    func.websearch_to_tsquery("russian", query)
                ),
            )
        )
        .order_by(desc("relevance"))
        .limit(limit)
    )

    db_products = await db.execute(stmt_products)
    for product, relevance in db_products.all():
        results.append(
            GlobalSearchResult(
                id=product.id,
                type=SearchType.product,
                title=product.title,
                description=product.description,
                relevance=float(relevance) if relevance else 0.0,
            )
        )

    course_similarity = func.similarity(Course.title, query).label("relevance")

    stmt_courses = (
        select(Course, course_similarity)
        .where(Course.is_published)
        .where(
            or_(
                Course.title.op("%")(query),
                Course.title.ilike(f"%{query}%"),
                Course.description.ilike(f"%{query}%"),
            )
        )
        .order_by(desc("relevance"))
        .limit(limit)
    )

    db_courses = await db.execute(stmt_courses)
    for course, relevance in db_courses.all():
        results.append(
            GlobalSearchResult(
                id=course.id,
                type=SearchType.course,
                title=course.title,
                description=course.description,
                relevance=float(relevance) if relevance else 0.5,
            )
        )

    """
    faq_similarity = func.similarity(FAQ.question, query).label("relevance")
    stmt_faq = select(FAQ, faq_similarity).where(FAQ.question.op("%")(query)).limit(limit)
    db_faq = await db.execute(stmt_faq)
    for faq, relevance in db_faq.all():
        results.append(
        GlobalSearchResult(
            id=faq.id, type="faq", title=faq.question, description=faq.answer, relevance=float(relevance)
        )
        )
    """
    results.sort(key=lambda x: x.relevance, reverse=True)
    return results[:limit]
