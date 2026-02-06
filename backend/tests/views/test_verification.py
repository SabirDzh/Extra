import pytest
from httpx import AsyncClient

@pytest.mark.anyio
async def test_verification_page(client: AsyncClient):
    response = await client.get("/verify-email/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
