import pytest
from httpx import AsyncClient

@pytest.mark.anyio
async def test_get_paths_stats(client: AsyncClient):
    await client.get("/api/v1/users")
    
    response = await client.get("/api/v1/service/stats")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
