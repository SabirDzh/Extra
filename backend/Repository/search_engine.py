from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Iterable, Literal, TypeVar

from rapidfuzz import fuzz

SearchIn = Literal["title", "description", "all", "filters"]
SearchSort = Literal["alphabet_asc", "alphabet_desc", "date_desc", "date_asc"]

T = TypeVar("T")

MIN_RELEVANCE_SCORE = 35.0
MAX_SEARCH_CANDIDATES = 2000
TITLE_WEIGHT = 4.5
DESCRIPTION_WEIGHT = 0.2
FILTERS_WEIGHT = 1.2


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


def is_title_prefix_match(query: str, title: str) -> bool:
    normalized_query = normalize_text(query)
    normalized_title = normalize_text(title)
    if not normalized_query or not normalized_title:
        return False
    if normalized_title == normalized_query:
        return False
    return normalized_title.startswith(normalized_query)


def prefix_title_matches(
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
        if is_title_prefix_match(normalized_query, title_getter(item) or "")
    ]


def compute_relevance_breakdown(
    query: str,
    title: str,
    description: str,
    search_in: SearchIn,
    filter_text: str = "",
) -> dict[str, float | bool]:
    normalized_query = normalize_text(query)
    normalized_title = normalize_text(title)
    normalized_description = normalize_text(description)
    normalized_filters = normalize_text(filter_text)

    title_score = _score_text(normalized_query, normalized_title)
    description_score = _score_text(normalized_query, normalized_description)
    filters_score = _score_text(normalized_query, normalized_filters)
    exact_title = bool(normalized_query and normalized_title == normalized_query)
    prefix_title = is_title_prefix_match(normalized_query, normalized_title)

    if search_in == "title":
        score = title_score * TITLE_WEIGHT
    elif search_in == "description":
        score = description_score
    elif search_in == "filters":
        score = max(filters_score * FILTERS_WEIGHT, title_score * 1.1)
    else:
        score = max(
            title_score * TITLE_WEIGHT,
            description_score * DESCRIPTION_WEIGHT,
            filters_score * FILTERS_WEIGHT,
        )

    return {
        "score": score,
        "exact_title": exact_title,
        "prefix_title": prefix_title,
        "title_score": title_score,
        "description_score": description_score,
        "filters_score": filters_score,
    }


def compute_relevance(
    query: str,
    title: str,
    description: str,
    search_in: SearchIn,
    filter_text: str = "",
) -> float:
    breakdown = compute_relevance_breakdown(
        query=query,
        title=title,
        description=description,
        search_in=search_in,
        filter_text=filter_text,
    )
    return float(breakdown["score"])


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


def is_title_substring_match(query: str, title: str) -> bool:
    normalized_query = normalize_text(query)
    normalized_title = normalize_text(title)
    if not normalized_query or not normalized_title:
        return False
    return normalized_query in normalized_title


def strict_title_matches(
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
        if is_title_substring_match(normalized_query, title_getter(item) or "")
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

    scored: list[tuple[tuple[float, ...], T]] = []
    for item in items:
        if search_in in {"title", "filters"}:
            if not is_title_substring_match(query, title_getter(item) or ""):
                continue
        elif search_in == "all":
            title = normalize_text(title_getter(item) or "")
            if not any(word in title for word in query.split()):
                continue
        breakdown = compute_relevance_breakdown(
            query=query,
            title=normalize_text(title_getter(item)),
            description=normalize_text(description_getter(item)),
            search_in=search_in,
            filter_text=normalize_text(filter_text_getter(item)) if filter_text_getter else "",
        )
        score = float(breakdown["score"])
        has_prefix = bool(breakdown["prefix_title"]) if search_in in {"title", "all", "filters"} else False
        if score >= MIN_RELEVANCE_SCORE or has_prefix:
            if search_in == "description":
                rank_key = (score,)
            elif search_in == "filters":
                rank_key = (
                    1.0 if has_prefix else 0.0,
                    score,
                )
            else:
                rank_key = (
                    1.0 if has_prefix else 0.0,
                    1.0 if float(breakdown["title_score"]) > 0 else 0.0,
                    float(breakdown["title_score"]),
                    score,
                )
            scored.append((rank_key, item))

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
