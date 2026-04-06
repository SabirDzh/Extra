"""
Стресс-тесты для Шага 6: фильтрация по audience через query-параметр.
GET /courses/?audience=installer — только курсы для монтажников.
GET /courses/?audience=everyone — только курсы для всех.
"""

import pytest
from httpx import AsyncClient


async def _create_course(
    client: AsyncClient, headers: dict, title: str, audience: str
) -> dict:
    resp = await client.post(
        "/api/v1/courses/",
        json={"title": title, "audience": audience, "is_published": True},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.anyio
async def test_filter_by_audience_installer_returns_only_installer(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 1: GET /courses/?audience=installer возвращает только
    курсы с audience=installer.
    """
    await _create_course(client, superuser_token_headers, "Aud Installer 1", "installer")
    await _create_course(client, superuser_token_headers, "Aud Everyone 1", "everyone")

    resp = await client.get("/api/v1/courses/?audience=installer")
    assert resp.status_code == 200
    courses = resp.json()
    assert len(courses) >= 1
    for course in courses:
        assert course["audience"] == "installer", (
            f"Фильтр audience=installer вернул курс с audience='{course['audience']}'"
        )


@pytest.mark.anyio
async def test_filter_by_audience_everyone_returns_only_everyone(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 2: GET /courses/?audience=everyone фильтрует корректно.
    """
    await _create_course(client, superuser_token_headers, "Aud Everyone 2", "everyone")
    await _create_course(client, superuser_token_headers, "Aud Installer 2", "installer")

    resp = await client.get("/api/v1/courses/?audience=everyone")
    assert resp.status_code == 200
    courses = resp.json()
    assert len(courses) >= 1
    for course in courses:
        assert course["audience"] == "everyone"


@pytest.mark.anyio
async def test_invalid_audience_filter_returns_422(
    client: AsyncClient,
):
    """
    Стресс-тест 3: Недопустимое значение audience → 422.
    """
    resp = await client.get("/api/v1/courses/?audience=vip")
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_audience_filter_in_search_endpoint(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 4: Фильтр audience работает и в /search эндпоинте.
    """
    await _create_course(client, superuser_token_headers, "Search Aud Course", "installer")

    resp = await client.get("/api/v1/courses/search?audience=installer")
    assert resp.status_code == 200
    courses = resp.json()
    for course in courses:
        assert course["audience"] == "installer"


@pytest.mark.anyio
async def test_audience_and_level_filters_combine(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 5: Комбинация audience=installer&level=beginner
    фильтрует по обоим параметрам одновременно.
    """
    await client.post(
        "/api/v1/courses/",
        json={
            "title": "Combo Installer Beginner",
            "audience": "installer",
            "level": "beginner",
            "is_published": True,
        },
        headers=superuser_token_headers,
    )
    await client.post(
        "/api/v1/courses/",
        json={
            "title": "Combo Everyone Advanced",
            "audience": "everyone",
            "level": "advanced",
            "is_published": True,
        },
        headers=superuser_token_headers,
    )

    resp = await client.get("/api/v1/courses/?audience=installer&level=beginner")
    assert resp.status_code == 200
    courses = resp.json()
    assert len(courses) >= 1
    for course in courses:
        assert course["audience"] == "installer"
        assert course["level"] == "beginner"


@pytest.mark.anyio
async def test_audience_label_is_correct_in_filtered_results(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 6: При фильтрации audience_label тоже верно показывается.
    """
    await _create_course(client, superuser_token_headers, "Label Filtered", "installer")

    resp = await client.get("/api/v1/courses/?audience=installer")
    assert resp.status_code == 200
    courses = resp.json()
    assert len(courses) >= 1
    for course in courses:
        assert course["audience_label"] == "Монтажник"
