import uuid
from typing import Any, List

from core.models.course import Course
from core.models.error import Error
from core.models.faq import FAQ
from core.models.product import Product
from core.models.term import Term
from core.models.recommendation import Recommendation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from Repository.search_engine import (
    MAX_SEARCH_CANDIDATES,
    SearchIn,
    SearchSort,
    compute_relevance,
    exact_title_matches,
    filter_and_rank_items,
    normalize_text,
    paginate_items,
    sort_items,
)


async def global_search_entities(
    session: AsyncSession,
    q: str | None = None,
    limit_per_category: int = 5,
    search_in: SearchIn = "all",
    sort: SearchSort = "alphabet_asc",
) -> dict:
    empty_result: dict[str, list[Any]] = {
        "courses": [],
        "products": [],
        "terms": [],
        "errors": [],
        "faqs": [],
        "recommendations": [],
    }

    async def search_single_model(model):
        stmt = select(model).limit(MAX_SEARCH_CANDIDATES)


        if hasattr(model, "is_published"):
            stmt = stmt.where(model.is_published)

        title_field = getattr(model, "title", getattr(model, "question", None))
        desc_field = getattr(model, "description", getattr(model, "answer", None))

        result = await session.execute(stmt)
        items = list(result.scalars().all())

        if not title_field or not desc_field:
            paged = paginate_items(items, 0, limit_per_category)
            return {
                "items": paged,
                "top_score": 0.0,
                "has_exact": False,
            }

        title_getter = lambda item: getattr(item, title_field.key, "")
        desc_getter = lambda item: getattr(item, desc_field.key, "")

        ranked = filter_and_rank_items(
            items,
            q=q,
            search_in=search_in,
            title_getter=title_getter,
            description_getter=desc_getter,
        )
        sorted_items = sort_items(
            ranked,
            sort=sort,
            title_getter=title_getter,
            date_getter=lambda item: getattr(item, "created_at", None),
        )
        paged_items = paginate_items(sorted_items, 0, limit_per_category)

        query = normalize_text(q)
        exact_items = exact_title_matches(items, query, title_getter) if query else []
        has_exact = len(exact_items) > 0
        top_score = 0.0
        if query and sorted_items:
            top = sorted_items[0]
            top_score = compute_relevance(
                query=query,
                title=normalize_text(title_getter(top)),
                description=normalize_text(desc_getter(top)),
                search_in=search_in,
            )

        return {
            "items": paged_items,
            "top_score": top_score,
            "has_exact": has_exact,
        }

    category_models = {
        "courses": Course,
        "products": Product,
        "terms": Term,
        "errors": Error,
        "faqs": FAQ,
        "recommendations": Recommendation,
    }

    category_results: dict[str, dict[str, Any]] = {}
    for category_name, model in category_models.items():
        category_results[category_name] = await search_single_model(model)

    if not q or not q.strip():
        return {
            key: value["items"]
            for key, value in category_results.items()
        }

    exact_categories = [
        key for key, value in category_results.items() if value["has_exact"]
    ]
    if exact_categories:
        result = empty_result.copy()
        for key in exact_categories:
            result[key] = category_results[key]["items"]
        return result

    best_category = max(
        category_results.items(),
        key=lambda item: item[1]["top_score"],
    )[0]
    if category_results[best_category]["top_score"] <= 0:
        return empty_result

    result = empty_result.copy()
    result[best_category] = category_results[best_category]["items"]
    return result
