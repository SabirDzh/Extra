import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_products(client: AsyncClient):
    # Using default pagination
    response = await client.get("/api/v1/products/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.anyio
async def test_create_product_as_admin(client: AsyncClient, superuser_token_headers):
    payload = {
        "title": "Oscilloscope X2",
        "description": "Powerful scope",
        "attributes": {"bandwidth": "200MHz"},
        "image_url": ["http://img1.jpg"],
    }
    response = await client.post(
        "/api/v1/products/", json=payload, headers=superuser_token_headers
    )
    assert response.status_code == 201
    assert response.json()["title"] == payload["title"]


@pytest.mark.anyio
async def test_create_duplicate_product_error(
    client: AsyncClient, superuser_token_headers
):
    payload = {
        "title": "Duplicate Product Title",
        "description": "Desc",
        "attributes": {},
        "image_url": [],
    }
    # First creation
    await client.post(
        "/api/v1/products/", json=payload, headers=superuser_token_headers
    )

    # Second creation with same title
    response = await client.post(
        "/api/v1/products/", json=payload, headers=superuser_token_headers
    )
    assert response.status_code == 409


@pytest.mark.anyio
async def test_search_products(client: AsyncClient):
    # Search requires 'q' in query params, and also expects pagination params (limit, offset)
    response = await client.get("/api/v1/products/search?q=scope&limit=10&offset=0")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.anyio
async def test_update_product_as_admin(client: AsyncClient, superuser_token_headers):
    # Create first
    payload = {
        "title": "Initial Product",
        "description": "Desc",
        "attributes": {},
        "image_url": [],
    }
    create_resp = await client.post(
        "/api/v1/products/", json=payload, headers=superuser_token_headers
    )
    product_id = create_resp.json()["id"]

    # Update (using PATCH as in the controller)
    update_payload = {"title": "Updated Product Title"}
    response = await client.patch(
        f"/api/v1/products/{product_id}",
        json=update_payload,
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Product Title"


@pytest.mark.anyio
async def test_delete_product_as_admin(client: AsyncClient, superuser_token_headers):
    # Create
    payload = {
        "title": "Product to Delete",
        "description": "Desc",
        "attributes": {},
        "image_url": [],
    }
    create_resp = await client.post(
        "/api/v1/products/", json=payload, headers=superuser_token_headers
    )
    product_id = create_resp.json()["id"]

    # Delete
    response = await client.delete(
        f"/api/v1/products/{product_id}", headers=superuser_token_headers
    )
    assert response.status_code == 204

    # Verify
    get_resp = await client.get(f"/api/v1/products/{product_id}")
    assert get_resp.status_code == 404
