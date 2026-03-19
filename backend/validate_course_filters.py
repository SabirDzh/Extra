import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import insert, delete, select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from core.config import settings
from core.models.course import Course, CourseEnrollment, CourseLevel
from core.models.user import User
from crud.course import search_courses

async def validate_filters():
    print("--- Валидация фильтров курсов ---")
    engine = create_async_engine(str(settings.db.url))
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    async with SessionLocal() as session:
        # 1. Подготовка: найдем или создадим тестового пользователя
        user_stmt = select(User).limit(1)
        user = (await session.execute(user_stmt)).scalar_one_or_none()
        if not user:
            print("Ошибка: В базе нет пользователей для теста.")
            return

        print(f"Используем пользователя: {user.email}")

        # 2. Очистка старых тестовых данных
        await session.execute(delete(Course).where(Course.title.like("TEST_FILTER_%")))
        await session.commit()

        # 3. Создание тестовых курсов
        now = datetime.now(timezone.utc)
        
        c1_id, c2_id, c3_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        
        test_data = [
            {
                "id": c1_id,
                "title": "TEST_FILTER_Beginner_Old",
                "description": "Old beginner course",
                "level": CourseLevel.beginner,
                "created_at": now - timedelta(days=2),
                "is_published": True,
                "created_by": user.id
            },
            {
                "id": c2_id,
                "title": "TEST_FILTER_Intermediate_New",
                "description": "Fresh intermediate course",
                "level": CourseLevel.intermediate,
                "created_at": now - timedelta(minutes=30),
                "is_published": True,
                "created_by": user.id
            },
            {
                "id": c3_id,
                "title": "TEST_FILTER_Advanced_Old",
                "description": "Old advanced course",
                "level": CourseLevel.advanced,
                "created_at": now - timedelta(days=5),
                "is_published": True,
                "created_by": user.id
            }
        ]
        
        await session.execute(insert(Course).values(test_data))
        
        # 4. Записи (Enrollments)
        # Пользователь в процессе на C1
        await session.execute(insert(CourseEnrollment).values({
            "id": uuid.uuid4(),
            "user_id": user.id,
            "course_id": c1_id,
            "enrolled_at": now
        }))
        
        # Пользователь завершил C3
        await session.execute(insert(CourseEnrollment).values({
            "id": uuid.uuid4(),
            "user_id": user.id,
            "course_id": c3_id,
            "enrolled_at": now - timedelta(days=1),
            "completed_at": now
        }))
        
        await session.commit()
        print("Тестовые данные созданы.")

        # 5. Тестирование фильтров
        print("\nПроверка фильтров:")
        
        # Beginner
        results = await search_courses(session, filter_type="beginner")
        titles = [r.title for r in results if r.title.startswith("TEST_FILTER_")]
        print(f"   [beginner] Ожидаем Beginner_Old: {titles}")

        # New
        results = await search_courses(session, filter_type="new")
        titles = [r.title for r in results if r.title.startswith("TEST_FILTER_")]
        print(f"   [new] Ожидаем Intermediate_New: {titles}")

        # In Progress
        results = await search_courses(session, filter_type="in_progress", user_id=user.id)
        titles = [r.title for r in results if r.title.startswith("TEST_FILTER_")]
        print(f"   [in_progress] Ожидаем Beginner_Old: {titles}")

        # Completed
        results = await search_courses(session, filter_type="completed", user_id=user.id)
        titles = [r.title for r in results if r.title.startswith("TEST_FILTER_")]
        print(f"   [completed] Ожидаем Advanced_Old: {titles}")

        # Popular
        results = await search_courses(session, filter_type="popular")
        titles = [r.title for r in results if r.title.startswith("TEST_FILTER_")]
        print(f"   [popular] Ожидаем (Beginner_Old, Advanced_Old) первым списком: {titles}")

        # 6. Очистка
        await session.execute(delete(Course).where(Course.title.like("TEST_FILTER_%")))
        await session.commit()
        print("\nТестовые данные удалены.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(validate_filters())
