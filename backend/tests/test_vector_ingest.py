
import pytest
import pytest_asyncio
import uuid
import os
import json
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.vector_ingest import ingest_vector_file
from app.db import get_db_pool

# Setup Logger
logging.basicConfig(level=logging.INFO)

# Connect to local docker DB
base_url = os.getenv("DATABASE_URL", "postgresql://ideas_user:ideas_password@localhost:5433/ideas")
if base_url.startswith("postgresql://"):
    base_url = base_url.replace("postgresql://", "postgresql+asyncpg://")
elif base_url.startswith("postgres://"):
    base_url = base_url.replace("postgres://", "postgresql+asyncpg://")
TEST_DATABASE_URL = base_url

@pytest_asyncio.fixture
async def db_session():
    # Setup Engine
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

@pytest.mark.asyncio
async def test_vector_ingest_points(db_session, tmp_path):
    # 1. Create Dummy GeoJSON (Points)
    # Point in NYC (40.7128, -74.0060)
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"temp": 25.5},
                "geometry": {
                    "type": "Point",
                    "coordinates": [-74.0060, 40.7128]
                }
            }
        ]
    }
    
    file_path = tmp_path / "test_points.geojson"
    with open(file_path, "w") as f:
        json.dump(geojson_data, f)
        
    # 2. Run Ingest
    # We need to ensure DB pool is available to service. 
    # Service uses get_db_pool() which uses global pool. 
    # We might need to initialize it or override it.
    # Actually get_db_pool() just returns the global _pool. 
    # We need to init it.
    from app.db import close_db_pool
    # await init_db_pool() # Not needed, lazy init
    
    try:
        dataset_id = str(uuid.uuid4())
        # Insert dataset first (simulating uploads.py)
        await db_session.execute(text("INSERT INTO datasets (id, name, dggs_name) VALUES (:id, 'Vector Test', 'IVEA3H')"), {"id": dataset_id})
        await db_session.commit()
        
        # Ingest
        await ingest_vector_file(
            str(file_path),
            "Vector Test",
            dggs_name="IVEA3H",
            resolution=7,
            attr_key="temp",
            burn_attribute="temp",
            dataset_id=dataset_id
        )
        
        # 3. Verify
        # Check cell_objects
        res = await db_session.execute(text("SELECT dggid, value_num FROM cell_objects WHERE dataset_id = :id"), {"id": dataset_id})
        rows = res.fetchall()
        
        print("Ingested rows:", rows)
        assert len(rows) == 1
        assert rows[0][1] == 25.5
        # Verify DGGID is correct (NYC area)
        # We don't know exact ID but it should be a string
        assert isinstance(rows[0][0], str)
        assert len(rows[0][0]) > 2
        
    finally:
        await close_db_pool()

@pytest.mark.asyncio
async def test_vector_ingest_polygons(db_session, tmp_path):
    # Polygon around loc
    # A small box 
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"cat": 5},
                "geometry": {
                    "type": "Polygon",
                    # Make it 1 degree box to ensure capture
                    "coordinates": [[
                        [-75.0, 40.0],
                        [-74.0, 40.0],
                        [-74.0, 41.0],
                        [-75.0, 41.0],
                        [-75.0, 40.0]
                    ]]
                }
            }
        ]
    }
    file_path = tmp_path / "test_poly.geojson"
    with open(file_path, "w") as f:
        json.dump(geojson_data, f)
        
    from app.db import close_db_pool
    # await init_db_pool()
    
    try:
        ds_id = str(uuid.uuid4())
        await db_session.execute(text("INSERT INTO datasets (id, name, dggs_name) VALUES (:id, 'Poly Test', 'IVEA3H')"), {"id": ds_id})
        await db_session.commit()
        
        # Ingest at higher res to ensure center point hits
        await ingest_vector_file(
            str(file_path), 
            "Poly Test", 
            resolution=9, # Reasonably fine to catch the small box
            attr_key="category",
            burn_attribute="cat",
            dataset_id=ds_id
        )
        
        # Verify
        res = await db_session.execute(text("SELECT count(*) FROM cell_objects WHERE dataset_id = :id"), {"id": ds_id})
        count = res.scalar()
        print("Polygon cells found:", count)
        assert count > 0

    finally:
        await close_db_pool()
