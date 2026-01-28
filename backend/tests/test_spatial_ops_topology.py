
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import Dataset, CellObject
from app.main import app
from app.db import get_db
from app.auth import get_current_user
import uuid
import os

# Reuse connection logic from test_spatial_ops_db
base_url = os.getenv("DATABASE_URL", "postgresql://ideas_user:ideas_password@localhost:5433/ideas")
if base_url.startswith("postgresql://"):
    base_url = base_url.replace("postgresql://", "postgresql+asyncpg://")
TEST_DATABASE_URL = base_url

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

@pytest_asyncio.fixture
async def async_client(db_session):
    async def override_get_db():
        yield db_session
    
    async def override_get_current_user():
        return {"id": "test_user_id", "email": "test@example.com"}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_spatial_buffer_topology(async_client: AsyncClient, db_session):
    # 1. Setup Data: Single Cell at Level 3
    # We need a valid DGGID that exists in topology. 
    # From populate logs, Level 3 has 272 zones. 
    # We assume 'N' (North Pole logic for ISEA3H/IVEA3H) root exists, children exist.
    # Let's verify a known ID or insert a dummy if topology has it.
    # Actually, the topology table MUST contain the DGGID for the join to work.
    # So we should query dgg_topology to find a valid ID to use as input.
    
    res = await db_session.execute(text("SELECT dggid FROM dgg_topology WHERE level = 3 LIMIT 1"))
    row = res.fetchone()
    if not row:
        pytest.skip("dgg_topology table empty or no level 3 cells. Run populate_topology.py first.")
    
    test_dggid = row[0]
    
    ds_id = uuid.uuid4()
    db_session.add(Dataset(id=ds_id, name="Test Buffer Input", dggs_name="IVEA3H", metadata_={'min_level': 3, 'max_level': 3}))
    await db_session.commit()
    
    await db_session.execute(text("""
        INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num) 
        VALUES (:did, :dggid, 0, 'val', 100)
    """), {"did": ds_id, "dggid": test_dggid})
    await db_session.commit()
    
    # 2. Call Buffer API
    payload = {
        "type": "buffer",
        "datasetAId": str(ds_id),
        "keyA": "val",
        "limit": 1 # 1-ring neighbors
    }
    
    response = await async_client.post("/api/ops/spatial", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"
    new_id = data["newDatasetId"]
    
    # 3. Verify
    # Buffer of 1 cell should enable neighbors.
    # Neighbors of a hexagon in ISEA3H are usually 6 (or 5 for pentagons, or 12 for base?).
    # Check count > 1
    res = await db_session.execute(text("SELECT count(*) FROM cell_objects WHERE dataset_id = :id"), {"id": new_id})
    count = res.scalar()
    print(f"Buffer result count: {count} for cell {test_dggid}")
    assert count > 1
    assert count <= 15 # Expecting ~7-13 depending on definition (neighbors + self?)

@pytest.mark.asyncio
async def test_spatial_aggregate_topology(async_client: AsyncClient, db_session):
    # 1. Setup: Cells at Level 3 that share a parent
    # Find a parent at level 2, get its children from topology
    # Note: Topology table stores (dggid, neighbor). Where is Child->Parent stored?
    # Schema: (dggid, neighbor_dggid, parent_dggid, level)
    # The 'parent_dggid' column is populated.
    
    # Find a parent that has children in the topology table
    # Wait, dgg_topology is keyed by dggid. So for a given dggid, we have its parent.
    # Let's find a parent at level 2 (from topology of level 3 cells).
    res = await db_session.execute(text("SELECT parent_dggid FROM dgg_topology WHERE level = 3 AND parent_dggid IS NOT NULL LIMIT 1"))
    row = res.fetchone()
    if not row:
        pytest.skip("No parents found in topology.")
        
    parent_id = row[0]
    
    # Get all children that point to this parent
    res = await db_session.execute(text("SELECT DISTINCT dggid FROM dgg_topology WHERE parent_dggid = :pid"), {"pid": parent_id})
    children = [r[0] for r in res.fetchall()]
    
    if not children:
        pytest.skip("Parent has no children in topology??")

    ds_id = uuid.uuid4()
    db_session.add(Dataset(id=ds_id, name="Test Agg Input", dggs_name="IVEA3H", metadata_={'min_level': 3, 'max_level': 3}))
    await db_session.commit()
    
    # Insert children with values
    # We'll insert value 10 for all. Average should be 10.
    values = []
    for child in children:
        values.append({"did": ds_id, "dggid": child, "val": 10})
        
    await db_session.execute(text("""
        INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num) 
        VALUES (:did, :dggid, 0, 'val', :val)
    """), values)
    await db_session.commit()
    
    # 2. Call Aggregate API
    payload = {
        "type": "aggregate",
        "datasetAId": str(ds_id),
        "keyA": "val"
    }
    
    response = await async_client.post("/api/ops/spatial", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    new_id = data["newDatasetId"]
    
    # 3. Verify
    # Should reduce to 1 cell (the parent)
    res = await db_session.execute(text("SELECT dggid, value_num FROM cell_objects WHERE dataset_id = :id"), {"id": new_id})
    rows = res.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == parent_id
    assert rows[0][1] == 10.0
