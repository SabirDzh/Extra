import pytest
from httpx import AsyncClient
import uuid

@pytest.mark.anyio
async def test_list_errors(client: AsyncClient):
    # Testing with default pagination
    response = await client.get("/api/v1/error")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.anyio
async def test_create_error_as_admin(client: AsyncClient, superuser_token_headers):
    payload = {
        "title": "Database Error",
        "description": "Connection to the database failed.",
        "order_index": 1,
        "is_published": True,
    }
    response = await client.post(
        "/api/v1/error", json=payload, headers=superuser_token_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert "id" in data

@pytest.mark.anyio
async def test_create_duplicate_error_title(client: AsyncClient, superuser_token_headers):
    payload = {"title": "Duplicate Error", "description": "Desc", "order_index": 0}
    # First creation
    await client.post("/api/v1/error", json=payload, headers=superuser_token_headers)

    # Second creation with same title
    response = await client.post(
        "/api/v1/error", json=payload, headers=superuser_token_headers
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]

@pytest.mark.anyio
async def test_update_error_as_admin(client: AsyncClient, superuser_token_headers):
    # Create first
    create_resp = await client.post(
        "/api/v1/error",
        json={"title": "Old Error Title", "description": "Old Desc", "order_index": 0},
        headers=superuser_token_headers,
    )
    error_id = create_resp.json()["id"]

    # Update (using PATCH as in the controller)
    update_payload = {"title": "New Error Title", "description": "New Desc"}
    response = await client.patch(
        f"/api/v1/error/{error_id}", json=update_payload, headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New Error Title"

@pytest.mark.anyio
async def test_bulk_delete_errors(client: AsyncClient, superuser_token_headers):
    # Create two Errors
    e1 = await client.post(
        "/api/v1/error",
        json={"title": "Error 1", "description": "Desc 1", "order_index": 0},
        headers=superuser_token_headers,
    )
    e2 = await client.post(
        "/api/v1/error",
        json={"title": "Error 2", "description": "Desc 2", "order_index": 0},
        headers=superuser_token_headers,
    )

    id1 = e1.json()["id"]
    id2 = e2.json()["id"]

    # Bulk delete using DELETE method with query params as defined in controller
    response = await client.delete(
        f"/api/v1/error?list_error_id={id1}&list_error_id={id2}", headers=superuser_token_headers
    )
    assert response.status_code == 204

    # Verify deleted
    get_resp = await client.get(f"/api/v1/error/{id1}", headers=superuser_token_headers)
    assert get_resp.status_code == 404

@pytest.mark.anyio
async def test_get_error_admin(client: AsyncClient, superuser_token_headers):
    create_resp = await client.post(
        "/api/v1/error",
        json={"title": "Admin Error Test", "description": "Testing admin get", "order_index": 0},
        headers=superuser_token_headers,
    )
    error_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/error/{error_id}/admin", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert "created_by" in data
    assert "updated_at" in data
