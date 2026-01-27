
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.services import real_data_loader
from app.services.real_data_loader import load_countries, load_cities, HIERARCHY_LEVELS

# Mock dggal service
class MockDggalService:
    def list_zones_bbox(self, level, bbox):
        # Return mock DGGIDs. For testing, we just need unique IDs per level.
        return [f"L{level}_Z{i}" for i in range(5)] # 5 zones per level
    
    def get_centroid(self, dggid):
        return {"lat": 20.0, "lon": 20.0}

@pytest.fixture
def mock_dgg():
    return MockDggalService()

@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    repo.create.return_value = MagicMock(id="dataset-uuid")
    return repo

@pytest.fixture
def mock_session():
    session = AsyncMock()
    # Mock result for dataset_exists query
    # We want it to return False (None) so that loading proceeds
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    session.execute.return_value = mock_result
    return session

@pytest.mark.asyncio
async def test_load_countries_multi_res(mock_session, mock_repo, mock_dgg):
    # Mock HTTP response for GeoJSON
    mock_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"ADMIN": "TestCountry", "ISO_A3": "TST", "CONTINENT": "TestCont", "POP_EST": 100},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [0, 40], [40, 40], [40, 0], [0, 0]]]
                }
            }
        ]
    }

    with patch("app.services.real_data_loader.fetch_geojson", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_geojson
        
        # Determine strict or permissive depending on logic
        # Here we mock bulk_insert to verify calls
        with patch("app.services.real_data_loader.bulk_insert", new_callable=AsyncMock) as mock_bulk:
             with patch("app.services.real_data_loader.finalize_dataset", new_callable=AsyncMock):
                
                await load_countries(mock_session, mock_repo, mock_dgg, "admin-id")
                
                # Verification
                assert mock_bulk.call_count >= len(HIERARCHY_LEVELS) # Called at least once per level
                
                # Check that we generated data for all levels 1-6
                # We can inspect the calls to bulk_insert
                # Each call passes a list of values strings like "('dataset-uuid', 'L1_Z0', ...)"
                
                found_levels = set()
                for call in mock_bulk.call_args_list:
                    args, _ = call
                    values = args[2] # 3rd arg is values list
                    if not values: continue
                    
                    # Extract DGGID to check level based on our Mock logic (L{level}_...)
                    first_val = values[0]
                    # Format: ('uuid', 'dggid', ...)
                    parts = first_val.split("'")
                    if len(parts) >= 4:
                        dggid = parts[3]
                        if dggid.startswith("L"):
                            level = int(dggid.split("_")[0][1:])
                            found_levels.add(level)
                
                # Ensure we covered levels 1 to 6
                assert HIERARCHY_LEVELS == [1, 2, 3, 4, 5, 6]
                for lvl in HIERARCHY_LEVELS:
                    assert lvl in found_levels, f"Level {lvl} data was not generated"

@pytest.mark.asyncio
async def test_load_cities_multi_res(mock_session, mock_repo, mock_dgg):
    mock_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"NAME": "TestCity", "ADM0NAME": "TestCountry", "POP_MAX": 5000},
                "geometry": {
                    "type": "Point",
                    "coordinates": [0.0, 20.0] 
                }
            }
        ]
    }

    with patch("app.services.real_data_loader.fetch_geojson", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_geojson
        
        with patch("app.services.real_data_loader.bulk_insert", new_callable=AsyncMock) as mock_bulk:
             with patch("app.services.real_data_loader.finalize_dataset", new_callable=AsyncMock):
                
                await load_cities(mock_session, mock_repo, mock_dgg, "admin-id")
                
                found_levels = set()
                for call in mock_bulk.call_args_list:
                    args, _ = call
                    values = args[2]
                    if not values: continue
                    
                    first_val = values[0]
                    parts = first_val.split("'")
                    if len(parts) >= 4:
                        dggid = parts[3]
                        if dggid.startswith("L"):
                            level = int(dggid.split("_")[0][1:])
                            found_levels.add(level)
                
                for lvl in HIERARCHY_LEVELS:
                    assert lvl in found_levels, f"Level {lvl} city data was not generated"
