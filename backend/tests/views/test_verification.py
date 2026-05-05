import pytest
from httpx import AsyncClient

@pytest.mark.anyio
async def test_verification_page(client: AsyncClient):
    response = await client.get("/verify-email/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.anyio
async def test_verification_redirects_to_frontend_when_token_present(client: AsyncClient):
    token = "sample_token_123"
    response = await client.get(f"/verify-email/?token={token}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == f"https://extra-rho-six.vercel.app/?token={token}"
