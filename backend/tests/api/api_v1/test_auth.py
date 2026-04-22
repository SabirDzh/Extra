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
