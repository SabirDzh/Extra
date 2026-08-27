import logging
from typing import Any

from core.models.course import Course
from core.models.error import Error
from core.models.faq import FAQ
from core.models.product import Product
from core.models.term import Term
from core.models.recommendation import Recommendation
from Domain.Enums.user_role import UserRole
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from Services.course_access import apply_course_access_policy, get_course_access_policy
from Repository.search_engine import (
    MAX_SEARCH_CANDIDATES,
    MIN_RELEVANCE_SCORE,
    SearchIn,
    SearchSort,
    compute_relevance_breakdown,
    filter_and_rank_items,
    normalize_text,
    paginate_items,
    prefix_title_matches,
    sort_items,
)

logger = logging.getLogger(__name__)

CATEGORY_ABS_MIN_SCORE = 45.0
CATEGORY_NEAR_RATIO = 0.72
CATEGORY_SIGNAL_ABS_MIN_SCORE = 60.0
CATEGORY_SIGNAL_NEAR_RATIO = 0.84


async def global_search_entities(
    session: AsyncSession,
    q: str | None = None,
    limit_per_category: int = 5,
    search_in: SearchIn = "all",
    sort: SearchSort = "alphabet_asc",
    debug: bool = False,
    user_role: UserRole | None = None,
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

        if model is Course:
            stmt = apply_course_access_policy(
                stmt,
                get_course_access_policy(
                    user_role,
                    include_unpublished_for_admin=user_role == UserRole.admin,
                ),
            )
        elif hasattr(model, "is_published"):
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
                "has_prefix": False,
            }

        title_getter = lambda item: getattr(item, title_field.key, "")
        desc_getter = lambda item: getattr(item, desc_field.key, "")

        query = normalize_text(q)
        if not query:
            # Browse mode: deterministic client-facing ordering.
            sorted_items = sort_items(
                items,
                sort=sort,
                title_getter=title_getter,
                date_getter=lambda item: getattr(item, "created_at", None),
            )
            paged_items = paginate_items(sorted_items, 0, limit_per_category)
            return {
                "items": paged_items,
                "top_score": 0.0,
                "has_exact": False,
                "has_prefix": False,
            }

        # Query mode: relevance order only. UI order must not affect ranking.
        ranked_items = filter_and_rank_items(
            items,
            q=query,
            search_in=search_in,
            title_getter=title_getter,
            description_getter=desc_getter,
        )
        paged_items = paginate_items(ranked_items, 0, limit_per_category)

        has_exact = any(normalize_text(title_getter(item)) == query for item in items)
        has_prefix = len(prefix_title_matches(items, query, title_getter)) > 0
        top_score = 0.0
        if ranked_items:
            top = ranked_items[0]
            top_breakdown = compute_relevance_breakdown(
                query=query,
                title=normalize_text(title_getter(top)),
                description=normalize_text(desc_getter(top)),
                search_in=search_in,
            )
            top_score = float(top_breakdown["score"])

        return {
            "items": paged_items,
            "top_score": top_score,
            "has_exact": has_exact,
            "has_prefix": has_prefix,
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

    exact_categories = {k for k, v in category_results.items() if v["has_exact"]}
    prefix_categories = {k for k, v in category_results.items() if v["has_prefix"]}
    category_scores = {k: float(v["top_score"]) for k, v in category_results.items()}
    best_category, best_score = max(category_scores.items(), key=lambda item: item[1])

    if debug or logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "global_search score map query=%r exact=%s prefix=%s scores=%s",
            q,
            sorted(exact_categories),
            sorted(prefix_categories),
            category_scores,
        )

    if best_score <= 0:
        return empty_result

    chosen_categories: set[str] = set()
    signal_categories = exact_categories | prefix_categories

    if signal_categories:
        signal_best_score = max(category_scores[k] for k in signal_categories)
        threshold = max(
            CATEGORY_SIGNAL_ABS_MIN_SCORE,
            signal_best_score * CATEGORY_SIGNAL_NEAR_RATIO,
        )
        chosen_categories = {
            k for k, score in category_scores.items() if score >= threshold
        }
        chosen_categories |= signal_categories
    else:
        threshold = max(CATEGORY_ABS_MIN_SCORE, best_score * CATEGORY_NEAR_RATIO)
        chosen_categories = {
            k for k, score in category_scores.items() if score >= threshold
        }
        if not chosen_categories and best_score >= MIN_RELEVANCE_SCORE:
            chosen_categories = {best_category}

    result = empty_result.copy()
    for key in chosen_categories:
        result[key] = category_results[key]["items"]
    return result
