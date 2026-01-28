
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
# ...
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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import Dataset, CellObject
from app.main import app
from app.db import get_db
from app.auth import get_current_user
import uuid
import os

# Connect to local docker DB
base_url = os.getenv("DATABASE_URL", "postgresql://ideas_user:ideas_password@localhost:5433/ideas")
if base_url.startswith("postgresql://"):
    base_url = base_url.replace("postgresql://", "postgresql+asyncpg://")
elif base_url.startswith("postgres://"):
    base_url = base_url.replace("postgres://", "postgresql+asyncpg://")
TEST_DATABASE_URL = base_url

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    # Cleanup? Transactions are usually rolled back in tests but here we persist for verification logic.
    # For now, we leave data or manual cleanup.




@pytest.mark.asyncio
async def test_spatial_intersection_persistence(async_client: AsyncClient, db_session):
    # 1. Setup Data
    ds_id_a = uuid.uuid4()
    ds_id_b = uuid.uuid4()
    
    # Create Datasets
    db_session.add(Dataset(id=ds_id_a, name="DS_A", dggs_name="IVEA3H", metadata_={'min_level': 3, 'max_level': 3}))
    db_session.add(Dataset(id=ds_id_b, name="DS_B", dggs_name="IVEA3H", metadata_={'min_level': 3, 'max_level': 3}))
    await db_session.commit()
    
    # Create Overlapping Cells
    # Cell 1: In both
    # Cell 2: In A only
    # Cell 3: In B only
    
    await db_session.execute(text("""
        INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num) VALUES
        (:da, 'H3', 0, 'val', 10),
        (:da, 'H4', 0, 'val', 20),
        (:db, 'H3', 0, 'val', 30),
        (:db, 'H5', 0, 'val', 40)
    """), {"da": ds_id_a, "db": ds_id_b})
    await db_session.commit()
    
    # 2. Call API
    payload = {
        "type": "intersection",
        "datasetAId": str(ds_id_a),
        "datasetBId": str(ds_id_b),
        "keyA": "val",
        "keyB": "val"
    }
    
    response = await async_client.post("/api/ops/spatial", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"
    new_id = data["newDatasetId"]
    
    # 3. Verify Persistence
    # Check Dataset created
    res = await db_session.execute(text("SELECT name FROM datasets WHERE id = :id"), {"id": new_id})
    row = res.fetchone()
    assert row is not None
    assert row[0] == "Intersection Result"
    
    # Check Cells (Intersection of H3 should exist, Mean value (10+30)/2 = 20)
    res = await db_session.execute(text("SELECT dggid, value_num FROM cell_objects WHERE dataset_id = :id"), {"id": new_id})
    rows = res.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 'H3'
    assert rows[0][1] == 20.0

@pytest.mark.asyncio
async def test_spatial_difference_persistence(async_client: AsyncClient, db_session):
    # Setup similar to above
    ds_id_a = uuid.uuid4()
    ds_id_b = uuid.uuid4()
    db_session.add(Dataset(id=ds_id_a, name="DS_A", dggs_name="IVEA3H", metadata_={'min_level': 3, 'max_level': 3}))
    db_session.add(Dataset(id=ds_id_b, name="DS_B", dggs_name="IVEA3H", metadata_={'min_level': 3, 'max_level': 3}))
    await db_session.commit()
    
    await db_session.execute(text("""
        INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num) VALUES
        (:da, 'H3', 0, 'val', 10), -- Overlap
        (:da, 'H4', 0, 'val', 20), -- A Only
        (:db, 'H3', 0, 'val', 30)
    """), {"da": ds_id_a, "db": ds_id_b})
    await db_session.commit()
    
    payload = {
        "type": "difference",
        "datasetAId": str(ds_id_a),
        "datasetBId": str(ds_id_b),
        "keyA": "val",
        "keyB": "val"
    }
    response = await async_client.post("/api/ops/spatial", json=payload)
    assert response.status_code == 200
    new_id = response.json()["newDatasetId"]
    
    # Verify: H4 should remain. H3 (overlap) removed.
    res = await db_session.execute(text("SELECT dggid FROM cell_objects WHERE dataset_id = :id"), {"id": new_id})
    rows = res.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 'H4'

@pytest.mark.asyncio
async def test_spatial_union_persistence(async_client: AsyncClient, db_session):
    # Setup
    ds_id_a = uuid.uuid4()
    ds_id_b = uuid.uuid4()
    db_session.add(Dataset(id=ds_id_a, name="DS_A", dggs_name="IVEA3H", metadata_={'min_level': 3, 'max_level': 3}))
    db_session.add(Dataset(id=ds_id_b, name="DS_B", dggs_name="IVEA3H", metadata_={'min_level': 3, 'max_level': 3}))
    await db_session.commit()
    
    await db_session.execute(text("""
        INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num) VALUES
        (:da, 'H3', 0, 'val', 10),
        (:da, 'H4', 0, 'val', 20),
        (:db, 'H3', 0, 'val', 30),
        (:db, 'H5', 0, 'val', 40)
    """), {"da": ds_id_a, "db": ds_id_b})
    await db_session.commit()
    
    payload = {
        "type": "union",
        "datasetAId": str(ds_id_a),
        "datasetBId": str(ds_id_b),
        "keyA": "val",
        "keyB": "val"
    }
    response = await async_client.post("/api/ops/spatial", json=payload)
    assert response.status_code == 200
    new_id = response.json()["newDatasetId"]
    
    # Verify: H3, H4, H5 should exist. 
    # H3 will come from A (impl logic: Insert A, then B where not exists).
    
    res = await db_session.execute(text("SELECT dggid FROM cell_objects WHERE dataset_id = :id ORDER BY dggid"), {"id": new_id})
    rows = [r[0] for r in res.fetchall()]
    assert sorted(rows) == ['H3', 'H4', 'H5']
