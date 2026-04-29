import pytest
import uuid
import time
from sqlalchemy import insert
from core.models.product import Product
from Services.product import search_products, get_products
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.anyio
async def test_search_performance(session: AsyncSession, benchmark):

    new_products = []
    for i in range(1000):
        new_products.append({
            "id": uuid.uuid4(),
            "title": f"Прибор контроля давления АКД-{i}",
            "description": f"Это подробное описание прибора номер {i}. Он предназначен для автоматизации насосов и защиты от сухого хода.",
            "attributes": {"Артикул": 1000 + i, "Модуль Wi-Fi": i % 2 == 0},
            "image_url": []
        })
    
    await session.execute(insert(Product).values(new_products))
    await session.commit()



    async def run_search():
        return await search_products(session, q="АКД насос", limit=20)



    start_time = time.perf_counter()
    for _ in range(10):
        await run_search()
    avg_time = (time.perf_counter() - start_time) / 10
    
    print(f"\nAverage Hybrid Search Time (1000 products): {avg_time:.4f}s")

@pytest.mark.anyio
async def test_import_performance(session: AsyncSession):

    new_products = []
    for i in range(500):
        new_products.append({
            "id": uuid.uuid4(),
            "title": f"Bulk Product {i} {uuid.uuid4()}",
            "description": "Test description for bulk import performance measurements.",
            "attributes": {"attr": True},
            "image_url": []
        })
    
    start_time = time.perf_counter()
    await session.execute(insert(Product).values(new_products))
    await session.commit()
    end_time = time.perf_counter()
    
    print(f"\nBulk Insert Time (500 products): {end_time - start_time:.4f}s")
