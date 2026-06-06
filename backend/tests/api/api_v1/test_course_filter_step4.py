"""
Стресс-тесты для Шага 4: filter_type="beginner" убран из API,
фильтрация по уровню только через ?level=beginner.
"""

import pytest
from httpx import AsyncClient


async def _create_course(auth_client: AsyncClient, headers: dict, title: str, level: str) -> dict:
    resp = await auth_client.post(
        "/api/v1/courses/",
        json={"title": title, "level": level, "is_published": True},
        headers=headers,
    )
    assert resp.status_code == 201, f"Не удалось создать курс: {resp.text}"
    return resp.json()





@pytest.mark.anyio
async def test_filter_type_beginner_now_returns_422(
    auth_client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 1: После удаления, filter_type="beginner" должен вернуть 422.
    Фронтенд больше не может использовать этот старый параметр.
    """
    resp = await auth_client.get("/api/v1/courses/?filter_type=beginner")
    assert resp.status_code == 422, (
        f"Ожидали 422 для filter_type=beginner, получили {resp.status_code}: {resp.text}"
    )


@pytest.mark.anyio
async def test_filter_type_beginner_in_search_returns_422(
    auth_client: AsyncClient,
):
    """
    Стресс-тест 2: В /search filter_type=beginner тоже должен давать 422.
    """
    resp = await auth_client.get("/api/v1/courses/search?filter_type=beginner")
    assert resp.status_code == 422, (
        f"Ожидали 422 для filter_type=beginner в search, получили {resp.status_code}"
    )


@pytest.mark.anyio
async def test_level_beginner_still_works_via_level_param(
    auth_client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 3: Фильтрация начинающих через ?level=beginner должна
    работать корректно — это единственный правильный способ после Шага 4.
    """
    await _create_course(auth_client, superuser_token_headers, "Still Works Beginner", "beginner")
    await _create_course(auth_client, superuser_token_headers, "Still Works Advanced", "advanced")

    resp = await auth_client.get("/api/v1/courses/?level=beginner")
    assert resp.status_code == 200

    courses = resp.json()
    assert len(courses) >= 1
    for course in courses:
        assert course["level"] == "beginner"


@pytest.mark.anyio
async def test_valid_filter_types_still_work(
    auth_client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 4: Остальные допустимые filter_type (new, popular) остались
    рабочими после удаления beginner. Проверяем что мы ничего лишнего не сломали.
    """
    for ft in ["new", "popular"]:
        resp = await auth_client.get(f"/api/v1/courses/?filter_type={ft}")
        assert resp.status_code == 200, (
            f"filter_type={ft} вернул {resp.status_code} вместо 200"
        )


@pytest.mark.anyio
async def test_level_and_filter_type_can_combine(
    auth_client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 5: level и filter_type можно комбинировать независимо.
    Например level=beginner&filter_type=popular — должен вернуть 200.
    """
    await _create_course(
        auth_client, superuser_token_headers, "Combo Beginner Popular", "beginner"
    )

    resp = await auth_client.get("/api/v1/courses/?level=beginner&filter_type=popular")
    assert resp.status_code == 200

    courses = resp.json()
    for course in courses:
        assert course["level"] == "beginner"


@pytest.mark.anyio
async def test_filter_type_unknown_value_returns_422(
    auth_client: AsyncClient,
):
    """
    Стресс-тест 6: Любое неизвестное значение filter_type возвращает 422.
    Проверяет что после рефакторинга Pydantic-валидация осталась строгой.
    """
    for bad_val in ["beginner", "expert", "master", "noob", "superuser"]:
        resp = await auth_client.get(f"/api/v1/courses/?filter_type={bad_val}")
        assert resp.status_code == 422, (
            f"filter_type={bad_val} должен давать 422, получили {resp.status_code}"
        )
