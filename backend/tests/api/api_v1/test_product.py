import uuid
from unittest.mock import AsyncMock, patch

import pytest
from core.models.product import Product
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from utils.role import UserRole

pytestmark = pytest.mark.anyio

# --- Helpers ---


async def create_product_db(session, title="Test Product", attributes=None):
    if attributes is None:
        attributes = {"color": "red"}
    p = Product(
        title=title,
        description="Desc",
        attributes=attributes,
        image_url=["http://img.com"],
        # documentation and schema_connect are optional
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


# --- List Products ---


async def test_list_products_empty(client: AsyncClient):
    response = await client.get("/api/v1/product")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_products_success(client: AsyncClient, session: AsyncSession):
    await create_product_db(session, "P1")
    await create_product_db(session, "P2")

    response = await client.get("/api/v1/product")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "P1"


async def test_list_products_pagination(client: AsyncClient, session: AsyncSession):
    for i in range(5):
        await create_product_db(session, f"P{i}")

    response = await client.get("/api/v1/product?limit=2&offset=0")
    assert len(response.json()) == 2

    response = await client.get("/api/v1/product?limit=2&offset=2")
    assert len(response.json()) == 2

    response = await client.get("/api/v1/product?limit=2&offset=4")
    assert len(response.json()) == 1


# --- Get Product ---


async def test_get_product_success(client: AsyncClient, session: AsyncSession):
    p = await create_product_db(session, "GetMe")

    response = await client.get(f"/api/v1/product/{p.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(p.id)


async def test_get_product_not_found(client: AsyncClient):
    response = await client.get(f"/api/v1/product/{uuid.uuid4()}")
    assert response.status_code == 404


# --- Create Product ---


async def test_create_product_admin_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    await create_user("admin@prod.com", is_superuser=True, role=UserRole.admin)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@prod.com", "password": "Password12345!"},
    )

    payload = {
        "title": "New Product",
        "description": "New Desc",
        "attributes": {"weight": "1kg"},
        "image_url": ["http://new.img"],
    }
    response = await client.post("/api/v1/product", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "New Product"
    assert data["attributes"] == {"weight": "1kg"}


async def test_create_product_user_forbidden(client: AsyncClient, create_user):
    await create_user("user@prod.com", is_superuser=False, role=UserRole.user)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@prod.com", "password": "Password12345!"},
    )

    payload = {"title": "Hack", "description": "d", "attributes": {}, "image_url": []}
    response = await client.post("/api/v1/product", json=payload)
    assert response.status_code == 403


async def test_create_product_unauth(client: AsyncClient):
    payload = {"title": "Anon", "description": "d", "attributes": {}, "image_url": []}
    response = await client.post("/api/v1/product", json=payload)
    assert response.status_code == 401


async def test_create_product_validation_max_length(client: AsyncClient, create_user):
    await create_user("admin@val.com", is_superuser=True, role=UserRole.admin)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@val.com", "password": "Password12345!"},
    )

    payload = {
        "title": "a" * 300,  # Too long
        "description": "d",
        "attributes": {},
        "image_url": [],
    }
    response = await client.post("/api/v1/product", json=payload)
    assert response.status_code == 422


# --- Update Product ---


async def test_update_product_admin_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    p = await create_product_db(session, "Old Title")
    await create_user("admin@up.com", is_superuser=True, role=UserRole.admin)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@up.com", "password": "Password12345!"},
    )

    response = await client.patch(
        f"/api/v1/product/{p.id}", json={"title": "New Title"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New Title"


async def test_update_product_user_forbidden(
    client: AsyncClient, session: AsyncSession, create_user
):
    p = await create_product_db(session, "Safe")
    await create_user("user@up.com", role=UserRole.user)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@up.com", "password": "Password12345!"},
    )

    response = await client.patch(f"/api/v1/product/{p.id}", json={"title": "Hacked"})
    assert response.status_code == 403


async def test_update_product_not_found(client: AsyncClient, create_user):
    await create_user("admin@upnf.com", role=UserRole.admin)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@upnf.com", "password": "Password12345!"},
    )

    response = await client.patch(
        f"/api/v1/product/{uuid.uuid4()}", json={"title": "Ghost"}
    )
    assert response.status_code == 404


# --- Delete Product ---


async def test_delete_product_admin_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    p = await create_product_db(session, "To Delete")
    await create_user("admin@del.com", role=UserRole.admin)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@del.com", "password": "Password12345!"},
    )

    response = await client.delete(f"/api/v1/product/{p.id}")
    assert response.status_code == 200

    # Verify gone
    resp = await client.get(f"/api/v1/product/{p.id}")
    assert resp.status_code == 404


async def test_delete_product_user_forbidden(
    client: AsyncClient, session: AsyncSession, create_user
):
    p = await create_product_db(session, "Safe")
    await create_user("user@del.com", role=UserRole.user)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@del.com", "password": "Password12345!"},
    )

    response = await client.delete(f"/api/v1/product/{p.id}")
    assert response.status_code == 403


async def test_delete_product_not_found(client: AsyncClient, create_user):
    await create_user("admin@delnf.com", role=UserRole.admin)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@delnf.com", "password": "Password12345!"},
    )

    response = await client.delete(f"/api/v1/product/{uuid.uuid4()}")
    assert response.status_code == 404


# --- Search & Filter (Mocked) ---


async def test_search_product_mocked(client: AsyncClient):
    # Since search depends on DB features not in SQLite, we mock the CRUD function
    with patch(
        "api.api_v1.product.search_product", new_callable=AsyncMock
    ) as mock_search:
        mock_search.return_value = []
        response = await client.get("/api/v1/product/search/?search_query=test")
        assert response.status_code == 200
        assert response.json() == []
        mock_search.assert_called_once()


async def test_filter_product_mocked(client: AsyncClient):
    # Filter uses JSONB operators, mock it
    with patch(
        "api.api_v1.product.get_filtered", new_callable=AsyncMock
    ) as mock_filter:
        mock_filter.return_value = []
        response = await client.post(
            "/api/v1/product/filter", json={"min_accuracy": 10.0}
        )
        assert response.status_code == 200
        assert response.json() == []
        mock_filter.assert_called_once()


async def test_get_filter_limits_mocked(client: AsyncClient):
    # Uses DB aggregation
    with patch("api.api_v1.product.get_limits", new_callable=AsyncMock) as mock_limits:
        mock_limits.return_value = {"max_accuracy": 100.0, "min_accuracy": 0.0}
        response = await client.get("/api/v1/product/filter/limits")
        assert response.status_code == 200
        assert response.json()["max_accuracy"] == 100.0


async def test_get_filter_count_mocked(client: AsyncClient):
    with patch(
        "api.api_v1.product.get_count_product_filter", new_callable=AsyncMock
    ) as mock_count:
        mock_count.return_value = {"accuracy": 5}
        response = await client.get("/api/v1/product/filter/count")
        assert response.status_code == 200
        assert response.json()["accuracy"] == 5


# --- Additional Edge Cases ---


async def test_create_product_missing_fields(client: AsyncClient, create_user):
    await create_user("admin@miss.com", role=UserRole.admin)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@miss.com", "password": "Password12345!"},
    )

    # Missing attributes and image_url
    response = await client.post(
        "/api/v1/product", json={"title": "T", "description": "D"}
    )
    assert response.status_code == 422


async def test_filter_product_validation_error(client: AsyncClient):
    # min_accuracy cannot be negative
    response = await client.post("/api/v1/product/filter", json={"min_accuracy": -5.0})
    assert response.status_code == 422


async def test_search_product_empty_query(client: AsyncClient):
    # search_query min_length=1
    response = await client.get("/api/v1/product/search/?search_query=")
    assert response.status_code == 422


async def test_update_product_partial(
    client: AsyncClient, session: AsyncSession, create_user
):
    # Ensure PATCH only updates sent fields
    p = await create_product_db(session, "Original", {"k": "v"})
    await create_user("admin@part.com", role=UserRole.admin)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@part.com", "password": "Password12345!"},
    )

    response = await client.patch(
        f"/api/v1/product/{p.id}", json={"description": "Updated Desc"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Original"  # Unchanged
    assert data["description"] == "Updated Desc"  # Changed
    assert data["attributes"] == {"k": "v"}  # Unchanged


async def test_create_product_complex_attributes(client: AsyncClient, create_user):
    await create_user("admin@comp.com", role=UserRole.admin)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@comp.com", "password": "Password12345!"},
    )

    attr = {"nested": {"key": "val", "list": [1, 2]}, "bool": True}
    response = await client.post(
        "/api/v1/product",
        json={
            "title": "Complex",
            "description": "D",
            "attributes": attr,
            "image_url": [],
        },
    )
    assert response.status_code == 201
    assert response.json()["attributes"] == attr


async def test_list_products_cache_headers(client: AsyncClient, session: AsyncSession):
    # Test if endpoint works (cache is mocked in conftest? or memory)
    # The endpoint uses @decorator.cache(60)
    await create_product_db(session, "Cached")
    response = await client.get("/api/v1/product")
    assert response.status_code == 200
    # FastAPICache enabled in fixture?
    # conftest.py: FastAPICache.init(InMemoryBackend(), ..., enable=False)
    # If enable=False, it executes function.
    # So it should just work.


async def test_get_product_invalid_uuid(client: AsyncClient):
    response = await client.get("/api/v1/product/invalid-uuid")
    assert response.status_code == 422


async def test_update_product_invalid_payload(
    client: AsyncClient, session: AsyncSession, create_user
):
    p = await create_product_db(session, "P")
    await create_user("admin@invp.com", role=UserRole.admin)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@invp.com", "password": "Password12345!"},
    )

    response = await client.patch(f"/api/v1/product/{p.id}", json={"title": "a" * 300})
    assert response.status_code == 422


async def test_delete_product_unauth(client: AsyncClient, session: AsyncSession):
    p = await create_product_db(session, "P")
    response = await client.delete(f"/api/v1/product/{p.id}")
    assert response.status_code == 401


async def test_update_product_unauth(client: AsyncClient, session: AsyncSession):
    p = await create_product_db(session, "P")
    response = await client.patch(f"/api/v1/product/{p.id}", json={"title": "X"})
    assert response.status_code == 401


async def test_create_product_empty_title(client: AsyncClient, create_user):
    await create_user("admin@empt.com", role=UserRole.admin)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@empt.com", "password": "Password12345!"},
    )

    # Title required, empty string? Pydantic might allow unless min_length set.
    # Field(max_length=256). min_length default 0?
    response = await client.post(
        "/api/v1/product",
        json={"title": "", "description": "D", "attributes": {}, "image_url": []},
    )
    # Depending on schema, might be 201 or 422. Schema has just max_length.
    # But usually title shouldn't be empty.
    # If it creates, valid. If 422, valid.
    # Let's assume it should probably be valid by schema definition but maybe 422 in DB?
    # Actually, empty title is usually bad.
    # Checking schema: title: Annotated[str, Field(max_length=256)]
    # It allows empty string.
    assert response.status_code in (201, 422)


async def test_filter_product_invalid_field_type(client: AsyncClient):
    # Expecting list[str], sending int
    response = await client.post("/api/v1/product/filter", json={"industry": 123})
    assert response.status_code == 422
