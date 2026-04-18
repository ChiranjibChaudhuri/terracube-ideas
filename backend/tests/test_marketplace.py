import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
def async_client():
    """Create an async test client."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

@pytest.mark.asyncio
async def test_list_services(async_client: AsyncClient):
    """Test listing available services in the marketplace."""
    response = await async_client.get("/api/marketplace/services")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    service = data[0]
    assert service["id"] == "fire-spread"
    assert service["name"] == "Fire Spread Prediction"
    assert service["type"] == "ANALYTIC"
    assert "input_schema" in service
