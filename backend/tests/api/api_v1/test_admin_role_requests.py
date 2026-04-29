import uuid

import pytest
from httpx import AsyncClient

from core.config import settings
from core.models.admin_role_request import AdminRoleRequest, AdminRoleRequestStatus
from sqlalchemy import select


@pytest.mark.anyio
async def test_register_admin_role_creates_pending_request(client: AsyncClient, session):
    payload = {
        "email": "role_request_user@example.com",
        "password": "Password12345!",
        "role": "administrator",
        "fullname": "Request User",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "user"

    req = (await session.execute(
        select(AdminRoleRequest).where(AdminRoleRequest.user_id == uuid.UUID(body["id"]))
    )).scalar_one_or_none()
    assert req is not None


@pytest.mark.anyio
async def test_admin_can_approve_request_only_from_whitelist(client: AsyncClient, session, create_user):
    old_whitelist = settings.security.admin_role_whitelist
    settings.security.admin_role_whitelist = ["whitelist_user@example.com"]
    try:
        admin = await create_user(
            "approver@example.com",
            "Password12345!",
            is_superuser=True,
            role="administrator",
        )
        await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})

        target = await create_user("whitelist_user@example.com", "Password12345!", role="user")
        request = AdminRoleRequest(user_id=target.id, status=AdminRoleRequestStatus.pending)
        session.add(request)
        await session.commit()
        await session.refresh(request)

        list_resp = await client.get("/api/v1/users/admin-role-requests")
        assert list_resp.status_code == 200
        assert any(item["id"] == str(request.id) for item in list_resp.json())

        approve_resp = await client.patch(
            f"/api/v1/users/admin-role-requests/{request.id}",
            json={"approve": True},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "approved"
    finally:
        settings.security.admin_role_whitelist = old_whitelist
