import pytest
import uuid
import random
import string
import asyncio
from sqlalchemy import insert, select, func
from httpx import AsyncClient

from core.models.faq import FAQ
from core.models.product import Product
from main import main_app


def random_string(length=10):
    return "".join(random.choice(string.ascii_lowercase) for _ in range(length))


async def seed_data_if_needed(session, model, target_count=10000):
    """Generic data seeder that skips if enough data already exists."""
    count_stmt = select(func.count()).select_from(model)
    current_count = await session.scalar(count_stmt)

    if current_count >= target_count:
        return

    batch_size = 2000
    needed = target_count - current_count

    for _ in range(0, needed, batch_size):
        chunk_size = min(batch_size, needed)
        data = []
        for i in range(chunk_size):
            unique_id = uuid.uuid4()
            if model == FAQ:
                data.append(
                    {
                        "question": f"Question {random_string(10)} {unique_id}",
                        "answer": f"Answer {random_string(50)}",
                        "order_index": i,
                    }
                )
            elif model == Product:
                data.append(
                    {
                        "title": f"Product {random_string(10)} {unique_id}",
                        "description": f"Desc {random_string(100)}",
                        "attributes": {"attr": "val"},
                        "image_url": [],
                    }
                )

        await session.execute(insert(model).values(data))
        await session.commit()
        needed -= chunk_size


@pytest.mark.benchmark
@pytest.mark.anyio
class TestPerformanceSearch:
    """
    Performance benchmark suite for search operations.
    Uses anyio's blocking portal to run async code inside sync benchmark rounds.
    """

    async def _run_benchmark(self, benchmark, url: str, query: str):
        """Helper to bridge async search with sync benchmark fixture."""
        from anyio.from_thread import start_blocking_portal

        async def call_api():
            from httpx import ASGITransport
            # We use a new client instance to avoid loop-binding issues with shared fixtures
            async with AsyncClient(
                transport=ASGITransport(app=main_app), base_url="http://test"
            ) as ac:
                resp = await ac.get(f"{url}?q={query}&limit=20&offset=0")
                assert resp.status_code == 200
                return resp

        # Bridge async to sync for pytest-benchmark using a thread portal
        with start_blocking_portal() as portal:
            benchmark(portal.call, call_api)

    async def test_faq_search_performance_10k(
        self, client: AsyncClient, session, benchmark
    ):
        """Benchmark FAQ search with 10,000 records."""
        await seed_data_if_needed(session, FAQ, 10000)
        await self._run_benchmark(benchmark, "/api/v1/faq/search", "Question")

    async def test_product_search_performance_10k(
        self, client: AsyncClient, session, benchmark
    ):
        """Benchmark Product search with 10,000 records."""
        await seed_data_if_needed(session, Product, 10000)
        await self._run_benchmark(benchmark, "/api/v1/products/search", "Product")
