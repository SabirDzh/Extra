import pytest
from httpx import AsyncClient

@pytest.mark.anyio
async def test_get_users_list(client: AsyncClient, create_user):
    await create_user("user1@example.com")
    response = await client.get("/api/v1/users")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

@pytest.mark.anyio
async def test_read_users_me(client: AsyncClient, normal_user_token_headers):
    response = await client.get("/api/v1/users/me", headers=normal_user_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "normal@example.com"
