import asyncio
import time
import uuid
from sqlalchemy import insert, delete, text, select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from core.config import settings
from core.models.product import Product
from crud.product import search_products, get_products

async def run_benchmark():
    print(f"--- Начинаю тестирование производительности (PostgreSQL) ---")
    print(f"База данных: {str(settings.db.url).split('@')[-1]}") 
    
    engine = create_async_engine(str(settings.db.url))
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    async with SessionLocal() as session:

        print("\n1. Тестирование записи (Bulk Insert)...")
        test_products = []
        for i in range(1000):
            test_products.append({
                "id": uuid.uuid4(),
                "title": f"БЕНЧМАРК ПРИБОР {i} {uuid.uuid4().hex[:8]}",
                "description": f"Описание для теста производительности номер {i}. Насос, автоматика, давление, защита.",
                "attributes": {"Артикул": 900000 + i, "Тестовый": True},
                "image_url": []
            })
        
        start = time.perf_counter()
        await session.execute(insert(Product).values(test_products))
        await session.commit()
        write_time = time.perf_counter() - start
        print(f"   [OK] 1000 товаров создано за {write_time:.4f} сек ({1000/write_time:.1f} оп/сек)")


        print("\n2. Тестирование гибридного поиска (FTS + Trigram)...")
        queries = ["ПРИБОР", "насос давление", "БЕНЧМАРК", "900050"]
        total_search_time = 0
        
        for q in queries:
            start = time.perf_counter()
            results = await search_products(session, q=q, limit=20)
            elapsed = time.perf_counter() - start
            total_search_time += elapsed
            print(f"   [SEARCH] Запрос '{q}': {len(results)} результатов найдено за {elapsed:.4f} сек")
        
        avg_search = total_search_time / len(queries)
        print(f"   [AVG] Среднее время поиска: {avg_search:.4f} сек")


        print("\n3. Тестирование сортировки по JSONB Артикулу...")
        start = time.perf_counter()
        results = await get_products(session, sort_by="article", order="desc", limit=50)
        elapsed = time.perf_counter() - start
        print(f"   [SORT] Сортировка по артикулу (50 записей): {elapsed:.4f} сек")


        print("\n4. Очистка тестовых данных...")
        await session.execute(delete(Product).where(Product.title.like("БЕНЧМАРК %")))
        await session.commit()
        print("   [OK] Тестовые данные удалены.")

    await engine.dispose()
    print("\n--- Тестирование завершено ---")

if __name__ == "__main__":
    try:
        asyncio.run(run_benchmark())
    except Exception as e:
        print(f"\n[ERROR] Ошибка при запуске бенчмарка: {e}")
