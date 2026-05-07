from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Iterable, Literal, TypeVar

from rapidfuzz import fuzz

SearchIn = Literal["title", "description", "all", "filters"]
SearchSort = Literal["alphabet_asc", "alphabet_desc", "date_desc", "date_asc"]

T = TypeVar("T")

MIN_RELEVANCE_SCORE = 35.0
MAX_SEARCH_CANDIDATES = 2000


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.strip().lower().split())


def _score_text(query: str, text: str) -> float:
    if not query or not text:
        return 0.0
    return max(
        fuzz.ratio(query, text),
        fuzz.partial_ratio(query, text),
        fuzz.token_set_ratio(query, text),
    )


def compute_relevance(
    query: str,
    title: str,
    description: str,
    search_in: SearchIn,
    filter_text: str = "",
) -> float:
    title_score = _score_text(query, title)
    description_score = _score_text(query, description)
    filters_score = _score_text(query, filter_text)

    if search_in == "title":
        return title_score
    if search_in == "description":
        return description_score
    if search_in == "filters":
        return max(filters_score, title_score * 0.85)

    return max(title_score * 1.2, description_score, filters_score)


def exact_title_matches(
    items: Iterable[T],
    query: str,
    title_getter: Callable[[T], str | None],
) -> list[T]:
    normalized_query = normalize_text(query)
    if not normalized_query:
        return []
    return [
        item
        for item in items
        if normalize_text(title_getter(item)) == normalized_query
    ]


def sort_items(
    items: list[T],
    sort: SearchSort,
    title_getter: Callable[[T], str | None],
    date_getter: Callable[[T], datetime | None] | None = None,
) -> list[T]:
    if sort == "alphabet_asc":
        return sorted(items, key=lambda item: normalize_text(title_getter(item)))
    if sort == "alphabet_desc":
        return sorted(
            items,
            key=lambda item: normalize_text(title_getter(item)),
            reverse=True,
        )

    if date_getter:
        default_date = datetime.min
        if sort == "date_asc":
            return sorted(
                items,
                key=lambda item: (
                    date_getter(item) or default_date,
                    normalize_text(title_getter(item)),
                ),
            )
        return sorted(
            items,
            key=lambda item: (
                date_getter(item) or default_date,
                normalize_text(title_getter(item)),
            ),
            reverse=True,
        )

    return sort_items(items, "alphabet_asc", title_getter, None)


def filter_and_rank_items(
    items: list[T],
    q: str | None,
    search_in: SearchIn,
    title_getter: Callable[[T], str | None],
    description_getter: Callable[[T], str | None],
    filter_text_getter: Callable[[T], str] | None = None,
) -> list[T]:
    query = normalize_text(q)
    if not query:
        return items

    if search_in in {"title", "all", "filters"}:
        exact = exact_title_matches(items, query, title_getter)
        if exact:
            return exact

    scored: list[tuple[float, T]] = []
    for item in items:
        score = compute_relevance(
            query=query,
            title=normalize_text(title_getter(item)),
            description=normalize_text(description_getter(item)),
            search_in=search_in,
            filter_text=normalize_text(filter_text_getter(item)) if filter_text_getter else "",
        )
        if score >= MIN_RELEVANCE_SCORE:
            scored.append((score, item))

    scored.sort(key=lambda row: row[0], reverse=True)
    return [item for _, item in scored]


def paginate_items(items: list[T], offset: int, limit: int | None) -> list[T]:
    if limit is None:
        return items[offset:]
    return items[offset : offset + limit]


def attributes_to_search_text(attributes: dict[str, Any] | None) -> str:
    if not attributes:
        return ""
    chunks: list[str] = []
    for key, value in attributes.items():
        if value is True:
            chunks.append(str(key))
        elif isinstance(value, (str, int, float)):
            chunks.append(f"{key} {value}")
    return " ".join(chunks)
