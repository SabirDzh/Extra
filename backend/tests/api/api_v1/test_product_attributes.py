import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_product_attributes(client: AsyncClient):
    response = await client.get("/api/v1/product-attributes/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.anyio
async def test_create_product_attribute_as_admin(
    client: AsyncClient, superuser_token_headers
):
    payload = {
        "key": "Wi-Fi",
        "display_name": "Wi-Fi модуль",
        "data_type": "boolean",
        "sort_order": 1,
        "is_visible": True,
    }
    response = await client.post(
        "/api/v1/product-attributes/",
        json=payload,
        headers=superuser_token_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["key"] == "Wi-Fi"
    assert data["display_name"] == "Wi-Fi модуль"
    assert data["data_type"] == "boolean"
    assert data["is_visible"] is True


@pytest.mark.anyio
async def test_create_duplicate_product_attribute_error(
    client: AsyncClient, superuser_token_headers
):
    payload = {"key": "Bluetooth", "display_name": "Bluetooth"}
    await client.post(
        "/api/v1/product-attributes/",
        json=payload,
        headers=superuser_token_headers,
    )
    response = await client.post(
        "/api/v1/product-attributes/",
        json=payload,
        headers=superuser_token_headers,
    )
    assert response.status_code == 409


@pytest.mark.anyio
async def test_get_product_attribute(
    client: AsyncClient, superuser_token_headers
):
    payload = {"key": "GPS", "display_name": "GPS модуль"}
    create_resp = await client.post(
        "/api/v1/product-attributes/",
        json=payload,
        headers=superuser_token_headers,
    )
    attr_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/product-attributes/{attr_id}")
    assert response.status_code == 200
    assert response.json()["key"] == "GPS"


@pytest.mark.anyio
async def test_get_product_attribute_not_found(client: AsyncClient):
    response = await client.get(
        "/api/v1/product-attributes/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_update_product_attribute(
    client: AsyncClient, superuser_token_headers
):
    payload = {"key": "NFC", "display_name": "NFC"}
    create_resp = await client.post(
        "/api/v1/product-attributes/",
        json=payload,
        headers=superuser_token_headers,
    )
    attr_id = create_resp.json()["id"]

    update_payload = {
        "display_name": "NFC модуль",
        "sort_order": 5,
        "is_visible": False,
    }
    response = await client.patch(
        f"/api/v1/product-attributes/{attr_id}",
        json=update_payload,
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "NFC модуль"
    assert data["sort_order"] == 5
    assert data["is_visible"] is False


@pytest.mark.anyio
async def test_delete_product_attribute(
    client: AsyncClient, superuser_token_headers
):
    payload = {"key": "USB-C", "display_name": "USB-C"}
    create_resp = await client.post(
        "/api/v1/product-attributes/",
        json=payload,
        headers=superuser_token_headers,
    )
    attr_id = create_resp.json()["id"]

    response = await client.delete(
        f"/api/v1/product-attributes/{attr_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 204

    get_resp = await client.get(f"/api/v1/product-attributes/{attr_id}")
    assert get_resp.status_code == 404


@pytest.mark.anyio
async def test_delete_product_attribute_not_found(
    client: AsyncClient, superuser_token_headers
):
    response = await client.delete(
        "/api/v1/product-attributes/00000000-0000-0000-0000-000000000000",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_list_active_product_attributes(
    client: AsyncClient, superuser_token_headers
):
    await client.post(
        "/api/v1/product-attributes/",
        json={"key": "visible_attr", "is_visible": True},
        headers=superuser_token_headers,
    )
    await client.post(
        "/api/v1/product-attributes/",
        json={"key": "hidden_attr", "is_visible": False},
        headers=superuser_token_headers,
    )

    response = await client.get("/api/v1/product-attributes/")
    assert response.status_code == 200
    data = response.json()
    keys = [a["key"] for a in data]
    assert "visible_attr" in keys
    assert "hidden_attr" not in keys


@pytest.mark.anyio
async def test_list_all_attributes_as_admin(
    client: AsyncClient, superuser_token_headers
):
    await client.post(
        "/api/v1/product-attributes/",
        json={"key": "admin_visible", "is_visible": True},
        headers=superuser_token_headers,
    )
    await client.post(
        "/api/v1/product-attributes/",
        json={"key": "admin_hidden", "is_visible": False},
        headers=superuser_token_headers,
    )

    response = await client.get(
        "/api/v1/product-attributes/",
        params={"visible_only": False},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    keys = [a["key"] for a in data]
    assert "admin_visible" in keys
    assert "admin_hidden" in keys


@pytest.mark.anyio
async def test_non_admin_cannot_see_hidden_attributes(
    client: AsyncClient, superuser_token_headers
):
    await client.post(
        "/api/v1/product-attributes/",
        json={"key": "hidden_for_user", "is_visible": False},
        headers=superuser_token_headers,
    )

    client.cookies.clear()
    response = await client.get(
        "/api/v1/product-attributes/",
        params={"visible_only": False},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_sync_product_attributes(
    client: AsyncClient, superuser_token_headers
):
    product_payload = {
        "title": "Sync Test Product",
        "description": "Test",
        "attributes": {"sync_key_1": True, "sync_key_2": 42},
        "image_url": [],
    }
    await client.post(
        "/api/v1/products/",
        json=product_payload,
        headers=superuser_token_headers,
    )

    response = await client.post(
        "/api/v1/product-attributes/sync",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "created" in data
    assert "total" in data


@pytest.mark.anyio
async def test_create_product_auto_syncs_attributes(
    client: AsyncClient, superuser_token_headers
):
    payload = {
        "title": "Auto Sync Product",
        "description": "Test",
        "attributes": {"auto_sync_key": True},
        "image_url": [],
    }
    create_resp = await client.post(
        "/api/v1/products/",
        json=payload,
        headers=superuser_token_headers,
    )
    assert create_resp.status_code == 201

    attrs_resp = await client.get("/api/v1/product-attributes/")
    assert attrs_resp.status_code == 200
    keys = [a["key"] for a in attrs_resp.json()]
    assert "auto_sync_key" in keys


@pytest.mark.anyio
async def test_clear_all_product_attributes(
    client: AsyncClient, superuser_token_headers
):
    await client.post(
        "/api/v1/product-attributes/",
        json={"key": "clear_test_1"},
        headers=superuser_token_headers,
    )
    await client.post(
        "/api/v1/product-attributes/",
        json={"key": "clear_test_2"},
        headers=superuser_token_headers,
    )

    response = await client.delete(
        "/api/v1/product-attributes/clear",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "OK"

    list_resp = await client.get("/api/v1/product-attributes/")
    assert len(list_resp.json()) == 0


@pytest.mark.anyio
async def test_product_attributes_require_admin(
    client: AsyncClient,
):
    response = await client.post(
        "/api/v1/product-attributes/",
        json={"key": "test"},
    )
    assert response.status_code in (401, 403)


@pytest.mark.anyio
async def test_product_attribute_invalid_data_type(
    client: AsyncClient, superuser_token_headers
):
    response = await client.post(
        "/api/v1/product-attributes/",
        json={"key": "bad", "data_type": "invalid"},
        headers=superuser_token_headers,
    )
    assert response.status_code == 422
