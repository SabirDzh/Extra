import pytest
from httpx import AsyncClient

@pytest.mark.anyio
async def test_home_page(client: AsyncClient, normal_user_token_headers):
    response = await client.get("/home/", headers=normal_user_token_headers)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
