from dataclasses import dataclass, field
from typing import Awaitable, Callable

from core.config import settings
from fastapi import Request, Response


type CallNext = Callable[[Request], Awaitable[Response]]

@dataclass
class PathCounts:
    """Aggregated request and status counts for one bounded metric key."""

    count: int = 0
    statuses_counts: dict[int, int] = field(default_factory=dict)


class RequestsCountMiddlewareDispatch:
    """Collect a bounded set of per-route request statistics in memory."""

    _OTHER_PATH = "__other__"

    def __init__(self, max_paths: int | None = None) -> None:
        """Create a counter with a strict limit on distinct raw fallback paths.

        Args:
            max_paths: Maximum number of detailed paths before aggregation.
        """
        self.max_paths = max_paths or settings.observability.request_path_cardinality_limit
        self.counts: dict[str, PathCounts] = {}

    def _get_path_key(self, request: Request) -> str:
        """Use a resolved route template when Starlette has one available."""
        route = request.scope.get("route")
        return getattr(route, "path", None) or request.url.path

    def _get_path_counts(self, path: str) -> PathCounts:
        """Return a bounded metric bucket, merging unknown paths when full."""
        if path in self.counts:
            return self.counts[path]
        if len(self.counts) >= self.max_paths:
            return self.counts.setdefault(self._OTHER_PATH, PathCounts())
        return self.counts.setdefault(path, PathCounts())

    def _increment(self, request: Request, status_code: int) -> None:
        """Record a completed request in its route or bounded fallback bucket."""
        path_counts = self._get_path_counts(self._get_path_key(request))
        path_counts.count += 1
        path_counts.statuses_counts[status_code] = (
            path_counts.statuses_counts.get(status_code, 0) + 1
        )

    async def __call__(
        self,
        request: Request,
        call_next: CallNext,
    ) -> Response:
        try:
            response = await call_next(request)
        except Exception:
            self._increment(request, 999)
            raise
        self._increment(request, response.status_code)
        return response


requests_count_middleware_dispatch = RequestsCountMiddlewareDispatch()
