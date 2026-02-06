import pytest
from httpx import AsyncClient

@pytest.mark.anyio
async def test_register_user(client: AsyncClient):
    payload = {
        "email": "test@example.com",
        "password": "password12345",
        "role": "user",
        "username": {
            "first_name": "TestUser"
        },
        "is_active": True,
        "is_superuser": False,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["email"] == payload["email"]
    assert "id" in data

@pytest.mark.anyio
async def test_login_user(client: AsyncClient):
    # First register
    payload = {
        "email": "login@example.com",
        "password": "password12345",
        "role": "user",
        "username": {
            "first_name": "LoginUser"
        },
        "is_active": True,
        "is_verified": True # Assuming verification is needed or mocked?
    }
    # Create user directly or via API. API creates inactive/unverified usually depending on config.
    # But fastapi-users usually allows login if verified.
    # Let's check api/api_v1/auth.py logic or core/authentication.
    
    # Just register via API
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    
    # Login
    login_data = {
        "username": "login@example.com",
        "password": "password12345"
    }
    response = await client.post("/api/v1/auth/login", data=login_data)
    # If fails, it might be because user is not active or verified.
    # In a real scenario we'd need to verify the user or force it in DB.
    # For now let's see if it works. If 400, I'll need a helper to activate user.
    assert response.status_code == 204 or response.status_code == 200, response.text
    # Cookie transport usually sets a cookie
    assert len(response.cookies) > 0 or "access_token" in response.json()
