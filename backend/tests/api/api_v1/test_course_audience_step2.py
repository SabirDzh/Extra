"""
Стресс-тесты для Шага 2: поле audience — целевая аудитория курса.
Значения: "everyone" (Для всех) / "installer" (Монтажник).
Проверяется: создание, обновление, валидация неверных значений, дефолт.
"""

import pytest
from httpx import AsyncClient


# ─── Helpers ───────────────────────────────────────────────────────────────────


async def _create_course(client: AsyncClient, headers: dict, **kwargs) -> dict:
    payload = {
        "title": kwargs.get("title", "Audience Test Course"),
        "description": kwargs.get("description", ""),
        "is_published": True,
    }
    if "audience" in kwargs:
        payload["audience"] = kwargs["audience"]
    if "level" in kwargs:
        payload["level"] = kwargs["level"]

    resp = await client.post("/api/v1/courses/", json=payload, headers=headers)
    return resp


# ─── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_create_course_with_everyone_audience(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 1: Создание курса с audience="everyone". Поле должно возвращаться
    в ответе именно с этим значением.
    """
    resp = await _create_course(
        client, superuser_token_headers, title="Everyone Course", audience="everyone"
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "audience" in data, "Поле audience отсутствует в ответе!"
    assert data["audience"] == "everyone"


@pytest.mark.anyio
async def test_create_course_with_installer_audience(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 2: Создание курса с audience="installer". Должно сохраниться
    и вернуться корректно.
    """
    resp = await _create_course(
        client, superuser_token_headers, title="Installer Course", audience="installer"
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["audience"] == "installer"


@pytest.mark.anyio
async def test_create_course_default_audience_is_everyone(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 3: Если audience не указан при создании, должен быть дефолт
    "everyone" — а не null или ошибка. Проверяет что дефолт работает.
    """
    # не передаём audience вовсе
    resp = await client.post(
        "/api/v1/courses/",
        json={"title": "Default Audience Course", "is_published": True},
        headers=superuser_token_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "audience" in data
    assert data["audience"] == "everyone", (
        f"Ожидали дефолт 'everyone', получили '{data['audience']}'"
    )


@pytest.mark.anyio
async def test_invalid_audience_value_returns_422(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 4: Передача недопустимого значения audience должна вернуть 422,
    а не 500 или 201. Проверяет валидацию enum на уровне Pydantic.
    """
    resp = await client.post(
        "/api/v1/courses/",
        json={
            "title": "Bad Audience Course",
            "audience": "superadmin",  # не существует в enum
            "is_published": True,
        },
        headers=superuser_token_headers,
    )
    assert resp.status_code == 422, (
        f"Ожидали 422 для недопустимого audience, получили {resp.status_code}"
    )


@pytest.mark.anyio
async def test_update_course_audience_from_everyone_to_installer(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 5: Обновление audience с "everyone" на "installer".
    Поле должно изменяться через PUT /courses/{id}.
    """
    # Создаём курс с audience=everyone
    create_resp = await _create_course(
        client,
        superuser_token_headers,
        title="Update Audience Course",
        audience="everyone",
    )
    assert create_resp.status_code == 201
    course_id = create_resp.json()["id"]

    # Обновляем на installer
    update_resp = await client.put(
        f"/api/v1/courses/{course_id}",
        json={"audience": "installer"},
        headers=superuser_token_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["audience"] == "installer"


@pytest.mark.anyio
async def test_audience_persists_after_other_field_update(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 6: При обновлении другого поля (description), audience не должен
    сбрасываться к дефолту. Проверяет что partial update не затирает audience.
    """
    create_resp = await _create_course(
        client,
        superuser_token_headers,
        title="Persist Audience Course",
        audience="installer",
    )
    assert create_resp.status_code == 201
    course_id = create_resp.json()["id"]

    # Обновляем только description — audience не трогаем
    update_resp = await client.put(
        f"/api/v1/courses/{course_id}",
        json={"description": "Updated description only"},
        headers=superuser_token_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["audience"] == "installer", (
        "audience сбросился после обновления другого поля!"
    )


@pytest.mark.anyio
async def test_audience_field_present_in_list_endpoint(
    client: AsyncClient,
    superuser_token_headers: dict,
):
    """
    Стресс-тест 7: Поле audience должно присутствовать в каждом объекте
    при GET /courses/ (листинг), а не только при GET /courses/{id}.
    """
    await _create_course(
        client, superuser_token_headers, title="List Audience Test", audience="installer"
    )

    resp = await client.get("/api/v1/courses/")
    assert resp.status_code == 200

    courses = resp.json()
    assert len(courses) >= 1

    for course in courses:
        assert "audience" in course, (
            f"Курс {course.get('id')} не содержит поле audience в листинге!"
        )
        assert course["audience"] in ("everyone", "installer"), (
            f"Недопустимое значение audience: {course['audience']}"
        )
