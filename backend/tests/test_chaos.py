import pytest
import uuid
import json
from httpx import AsyncClient
# from app.main import app # Don't import app to avoid global state issues

# Helper to get auth token
async def get_auth_headers(ac: AsyncClient):
    login_res = await ac.post("/api/auth/login", json={
        "email": "admin@terracube.xyz",
        "password": "ChangeThisSecurePassword123!"
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_chaos_spatial_op_invalid_ids():
    # Hit the running server instead of in-process app to avoid loop issues
    async with AsyncClient(base_url="http://localhost:4000") as ac:
        headers = await get_auth_headers(ac)
        
        # Test invalid dataset A with random UUID
        bad_id = str(uuid.uuid4())
        res = await ac.post("/api/ops/spatial", json={
            "type": "intersection",
            "datasetAId": bad_id,
            "datasetBId": str(uuid.uuid4()),
            "keyA": "test",
            "keyB": "test"
        }, headers=headers)
        # Expect 400 (ValueError) or 404 (Not Found)
        assert res.status_code in [400, 404]
        assert "Dataset A not found" in res.json()["detail"]

@pytest.mark.asyncio
async def test_chaos_query_limit_caps():
    async with AsyncClient(base_url="http://localhost:4000") as ac:
        headers = await get_auth_headers(ac)

        # Get any valid dataset
        ds_res = await ac.get("/api/datasets", headers=headers)
        datasets = ds_res.json().get("datasets", [])
        
        if not datasets:
            pytest.skip("No datasets available to test query limits")
            
        ds_id = datasets[0]["id"]
        
        # Request absurdly high limit
        # Backend caps at 5000
        res = await ac.post("/api/ops/query", json={
            "type": "range",
            "datasetId": ds_id,
            "key": "test",
            "min": -999999,
            "limit": 1000000
        }, headers=headers)
        
        assert res.status_code == 200
        data = res.json()
        rows = data.get("rows", [])
        assert len(rows) <= 5000, "Limit capping failed"

@pytest.mark.asyncio
async def test_chaos_invalid_dggs_name():
    """Test that invalid DGGS name defaults safely instead of crashing."""
    async with AsyncClient(base_url="http://localhost:4000") as ac:
        headers = await get_auth_headers(ac)
        
        res = await ac.post("/api/toolbox/buffer", json={
            "dggids": ["A0"],
            "iterations": 1,
            "dggsName": "NON_EXISTENT_DGGS_SYSTEM"
        }, headers=headers)
        
        # Should default to IVEA3H (safe fallback) or return specific error
        # Current impl logs warning and uses IVEA3H
        assert res.status_code == 200
