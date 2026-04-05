"""
Стресс-тесты для Шага 3:
- Поле level_label возвращается для каждого курса с правильным русским значением
- Поле audience_label возвращается корректно
- Фильтрация по level через GET /courses/?level=... работает
- Несуществующий level возвращает 422
"""

import pytest
from httpx import AsyncClient


# ─── Helpers ───────────────────────────────────────────────────────────────────


async def _create_course(
    client: AsyncClient, headers: dict, title: str, level: str, audience: str = "everyone"
) -> dict:
    resp = await client.post(
        "/api/v1/courses/",
        json={"title": title, "level": level, "audience": audience, "is_published": True},
        headers=headers,
    )
    assert resp.status_code == 201, f"Не удалось создать курс: {resp.text}"
    return resp.json()


# ─── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_level_label_beginner_returns_russian(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 1: Курс с level=beginner должен возвращать
    level_label="Начинающий" в ответе.
    """
    course = await _create_course(
        client, superuser_token_headers, "Beginner Course", "beginner"
    )
    assert "level_label" in course, "Поле level_label отсутствует в ответе!"
    assert course["level_label"] == "Начинающий", (
        f"Ожидали 'Начинающий', получили '{course['level_label']}'"
    )


@pytest.mark.anyio
async def test_level_label_intermediate_returns_russian(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 2: level=intermediate → level_label="Продвинутый".
    """
    course = await _create_course(
        client, superuser_token_headers, "Intermediate Course", "intermediate"
    )
    assert course["level_label"] == "Продвинутый"


@pytest.mark.anyio
async def test_level_label_advanced_returns_russian(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 3: level=advanced → level_label="Эксперт".
    """
    course = await _create_course(
        client, superuser_token_headers, "Advanced Course", "advanced"
    )
    assert course["level_label"] == "Эксперт"


@pytest.mark.anyio
async def test_audience_label_present_in_response(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 4: Поле audience_label должно присутствовать и содержать
    русское название "Для всех" или "Монтажник".
    """
    course_everyone = await _create_course(
        client, superuser_token_headers, "Everyone Label Test", "beginner", "everyone"
    )
    course_installer = await _create_course(
        client, superuser_token_headers, "Installer Label Test", "beginner", "installer"
    )
    assert course_everyone["audience_label"] == "Для всех"
    assert course_installer["audience_label"] == "Монтажник"


@pytest.mark.anyio
async def test_filter_by_level_beginner_returns_only_beginners(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 5: GET /courses/?level=beginner должен вернуть только курсы
    с level="beginner", не возвращать intermediate или advanced.
    """
    await _create_course(client, superuser_token_headers, "Filter Beginner A", "beginner")
    await _create_course(client, superuser_token_headers, "Filter Beginner B", "beginner")
    await _create_course(client, superuser_token_headers, "Filter Advanced X", "advanced")
    await _create_course(client, superuser_token_headers, "Filter Intermediate Y", "intermediate")

    resp = await client.get("/api/v1/courses/?level=beginner")
    assert resp.status_code == 200

    courses = resp.json()
    assert len(courses) >= 2
    for course in courses:
        assert course["level"] == "beginner", (
            f"Фильтр level=beginner вернул курс с level='{course['level']}'"
        )


@pytest.mark.anyio
async def test_filter_by_level_advanced(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 6: GET /courses/?level=advanced возвращает только advanced курсы.
    """
    await _create_course(client, superuser_token_headers, "Adv Filter Course 1", "advanced")
    await _create_course(client, superuser_token_headers, "Beg Filter Course 1", "beginner")

    resp = await client.get("/api/v1/courses/?level=advanced")
    assert resp.status_code == 200

    courses = resp.json()
    assert len(courses) >= 1
    for course in courses:
        assert course["level"] == "advanced"


@pytest.mark.anyio
async def test_invalid_level_filter_returns_422(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 7: Передача недопустимого значения level возвращает 422,
    а не 500. Проверяет что FastAPI валидирует enum параметры запроса.
    """
    resp = await client.get("/api/v1/courses/?level=grandmaster")
    assert resp.status_code == 422, (
        f"Ожидали 422 для недопустимого level='grandmaster', получили {resp.status_code}"
    )


@pytest.mark.anyio
async def test_level_label_and_audience_label_in_list_endpoint(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 8: В листинге GET /courses/ у каждого объекта должны быть
    level_label и audience_label — убеждаемся что computed fields работают в списке.
    """
    await _create_course(
        client, superuser_token_headers, "List Labels Course", "intermediate", "installer"
    )

    resp = await client.get("/api/v1/courses/")
    assert resp.status_code == 200

    courses = resp.json()
    assert len(courses) >= 1

    for course in courses:
        assert "level_label" in course, f"Нет level_label у курса {course.get('id')}"
        assert "audience_label" in course, f"Нет audience_label у курса {course.get('id')}"
        assert course["level_label"] in ("Начинающий", "Продвинутый", "Эксперт")
        assert course["audience_label"] in ("Для всех", "Монтажник")


@pytest.mark.anyio
async def test_search_endpoint_supports_level_filter(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 9: GET /search?level=intermediate фильтрует правильно
    и не ломает поиск по тексту.
    """
    await _create_course(
        client, superuser_token_headers, "Search Intermediate Course", "intermediate"
    )
    await _create_course(
        client, superuser_token_headers, "Search Beginner Course", "beginner"
    )

    resp = await client.get("/api/v1/courses/search?level=intermediate")
    assert resp.status_code == 200

    courses = resp.json()
    for course in courses:
        assert course["level"] == "intermediate", (
            f"Search с level=intermediate вернул уровень '{course['level']}'"
        )
