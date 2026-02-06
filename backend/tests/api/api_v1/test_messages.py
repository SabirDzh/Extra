import pytest
from httpx import AsyncClient

@pytest.mark.anyio
async def test_get_user_messages(client: AsyncClient, normal_user_token_headers):
    response = await client.get("/api/v1/messages", headers=normal_user_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert "user" in data

@pytest.mark.anyio
async def test_get_superuser_messages_as_normal_user(client: AsyncClient, normal_user_token_headers):
    response = await client.get("/api/v1/messages/secrets", headers=normal_user_token_headers)
    assert response.status_code == 403

@pytest.mark.anyio
async def test_get_superuser_messages_as_superuser(client: AsyncClient, superuser_token_headers):
    response = await client.get("/api/v1/messages/secrets", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
