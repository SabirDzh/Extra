import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_register_user(client: AsyncClient):
    payload = {
        "email": "test@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": "TestUser",
        "is_active": True,
        "is_superuser": False,
        "is_verified": False,
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["email"] == payload["email"]
    assert data["fullname"] == payload["fullname"]
    assert "id" in data


@pytest.mark.anyio
async def test_login_user(client: AsyncClient):

    payload = {
        "email": "login@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": "LoginUser",
        "is_active": True,
        "is_verified": True,
    }





    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, resp.text


    login_data = {"username": "login@example.com", "password": "Password12345!"}
    response = await client.post("/api/v1/auth/login", data=login_data)



    assert response.status_code == 204 or response.status_code == 200, response.text

    assert len(response.cookies) > 0 or "access_token" in response.json()


@pytest.mark.anyio
async def test_auth_email_spaces_rejected(client: AsyncClient):
    # Registering with email containing spaces must fail (422)
    payload_leading_space = {
        "email": "  spaces_user@example.com  ",
        "password": "SecretPassword123!",
        "role": "user",
        "fullname": "SpaceUser",
    }
    response = await client.post("/api/v1/auth/register", json=payload_leading_space)
    assert response.status_code == 422

    payload_internal_space = {
        "email": "user name@example.com",
        "password": "SecretPassword123!",
        "role": "user",
        "fullname": "SpaceUser",
    }
    response = await client.post("/api/v1/auth/register", json=payload_internal_space)
    assert response.status_code == 422


@pytest.mark.anyio
async def test_auth_password_spaces_not_counted_towards_length(client: AsyncClient):
    # Password with only spaces or less than 4 non-space characters must fail (422)
    payload_spaces_only = {
        "email": "valid_user@example.com",
        "password": "    ",
        "role": "user",
        "fullname": "SpaceUser",
    }
    response = await client.post("/api/v1/auth/register", json=payload_spaces_only)
    assert response.status_code == 422

    payload_short_after_strip = {
        "email": "valid_user2@example.com",
        "password": "   a   ",
        "role": "user",
        "fullname": "SpaceUser",
    }
    response = await client.post("/api/v1/auth/register", json=payload_short_after_strip)
    assert response.status_code == 422

