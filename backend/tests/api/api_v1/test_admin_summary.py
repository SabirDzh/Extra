import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import User, UserBlockProgress, Block, CourseEnrollment
from datetime import datetime, timezone, timedelta

@pytest.mark.anyio
async def test_get_admin_summary_success(client: AsyncClient, superuser_token_headers: dict, session: AsyncSession):

    resp = await client.get("/api/v1/users/summary", headers=superuser_token_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users" in data
    assert "total_tests_passed" in data
    assert "course_stats" in data
    assert "new_users_stats" in data
    assert "count" in data["course_stats"]
    assert "percent" in data["course_stats"]

@pytest.mark.anyio
async def test_get_admin_summary_forbidden_for_regular_user(client: AsyncClient, create_user):
    await create_user("regular_stats@test.com", password="Password12345!")

    resp_login = await client.post("/api/v1/auth/login", data={"username": "regular_stats@test.com", "password": "Password12345!"})
    token = resp_login.cookies.get("fastapiusersauth", "")
    headers = {"cookie": f"fastapiusersauth={token}"}
    
    resp = await client.get("/api/v1/users/summary", headers=headers)
    assert resp.status_code == 403
