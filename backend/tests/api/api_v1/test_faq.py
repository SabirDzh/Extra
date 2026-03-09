import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_faqs(client: AsyncClient):
    # Testing with default pagination
    response = await client.get("/api/v1/faq/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.anyio
async def test_create_faq_as_admin(client: AsyncClient, superuser_token_headers):
    payload = {
        "question": "How to use this system?",
        "answer": "Read the docs.",
        "order_index": 1,
        "is_published": True,
    }
    response = await client.post(
        "/api/v1/faq/", json=payload, headers=superuser_token_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["question"] == payload["question"]
    assert "id" in data


@pytest.mark.anyio
async def test_create_duplicate_faq_error(client: AsyncClient, superuser_token_headers):
    payload = {"question": "Duplicate Question", "answer": "Answer"}
    # First creation
    await client.post("/api/v1/faq/", json=payload, headers=superuser_token_headers)

    # Second creation with same question
    response = await client.post(
        "/api/v1/faq/", json=payload, headers=superuser_token_headers
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.anyio
async def test_update_faq_as_admin(client: AsyncClient, superuser_token_headers):
    # Create first
    create_resp = await client.post(
        "/api/v1/faq/",
        json={"question": "Old Q", "answer": "Old A"},
        headers=superuser_token_headers,
    )
    faq_id = create_resp.json()["id"]

    # Update (using PATCH as in the controller)
    update_payload = {"question": "New Q", "answer": "New A"}
    response = await client.patch(
        f"/api/v1/faq/{faq_id}", json=update_payload, headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert response.json()["question"] == "New Q"


@pytest.mark.anyio
async def test_bulk_delete_faqs(client: AsyncClient, superuser_token_headers):
    # Create two FAQs
    f1 = await client.post(
        "/api/v1/faq/",
        json={"question": "Q1", "answer": "A1"},
        headers=superuser_token_headers,
    )
    f2 = await client.post(
        "/api/v1/faq/",
        json={"question": "Q2", "answer": "A2"},
        headers=superuser_token_headers,
    )

    id1 = f1.json()["id"]
    id2 = f2.json()["id"]

    # Bulk delete using DELETE method with query params as defined in controller
    response = await client.delete(
        f"/api/v1/faq/?data={id1}&data={id2}", headers=superuser_token_headers
    )
    assert response.status_code == 204

    # Verify deleted
    get_resp = await client.get(f"/api/v1/faq/{id1}")
    assert get_resp.status_code == 404
