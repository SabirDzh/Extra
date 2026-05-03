import pytest
from httpx import AsyncClient

@pytest.mark.anyio
async def test_get_users_list(client: AsyncClient, create_user, superuser_token_headers):
    await create_user("user1@example.com")
    response = await client.get("/api/v1/users", headers=superuser_token_headers)
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


@pytest.mark.anyio
async def test_admin_can_update_user_permissions(
    client: AsyncClient, create_user, superuser_token_headers
):
    user = await create_user("perm_target@example.com", role="buyer", is_superuser=False)
    resp = await client.patch(
        f"/api/v1/users/{user.id}/permissions",
        json={"role": "seller", "is_superuser": True},
        headers=superuser_token_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(user.id)
    assert body["role"] == "Продавец"
    assert body["is_superuser"] is True


@pytest.mark.anyio
async def test_non_admin_cannot_update_user_permissions(
    client: AsyncClient, create_user
):
    await create_user("non_admin_perm@example.com", role="buyer", is_superuser=False)
    target = await create_user("perm_target2@example.com", role="buyer", is_superuser=False)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "non_admin_perm@example.com", "password": "Password12345!"},
    )

    resp = await client.patch(
        f"/api/v1/users/{target.id}/permissions",
        json={"role": "seller", "is_superuser": True},
    )
    assert resp.status_code in (401, 403)
