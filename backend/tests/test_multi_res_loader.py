
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.real_data_loader import load_real_global_data, DATA_SOURCES

@pytest.fixture
def mock_pool():
    pool = MagicMock() # pool itself is sync object usually, but methods like execute are async
    # acquire() is sync, returns AsyncContextManager
    
    # We need acquire() to return an object that can be used in 'async with'
    # So acquire.return_value should have __aenter__ and __aexit__
    acquire_ctx = AsyncMock()
    pool.acquire.return_value = acquire_ctx
    
    conn = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    
    # Mock dataset existence check
    conn.fetchrow.return_value = None
    return pool

@pytest.mark.asyncio
async def test_load_real_global_data_orchestration(mock_pool):
    # Determine expected calls based on default DATA_SOURCES
    # World Countries: Vector, Min 1, Max 6 -> 6 calls
    # ETOPO1: Raster -> 1 call
    # WorldClim: Raster -> 1 call (if enabled)
    
    # We define a custom DATA_SOURCES for test stability or use the imported one.
    # Let's use the imported one but ensure we know what's in it.
    # Actually, let's patch DATA_SOURCES to be deterministic for the test.
    
    test_sources = [
        {
            "name": "Test Vector",
            "type": "vector",
            "url": "http://test.com/v.json",
            "file": "v.json",
            "dggs": "IVEA3H",
            "min_lvl": 1,
            "max_lvl": 3 # 3 levels
        },
        {
            "name": "Test Raster",
            "type": "raster",
            "url": "http://test.com/r.zip",
            "file": "r.zip",
            "target_tif": "r.tif",
            "attr": "val",
            "min_lvl": 1,
            "max_lvl": 2
        }
    ]
    
    with patch("app.services.real_data_loader.get_db_pool", return_value=mock_pool), \
         patch("app.services.real_data_loader.DATA_SOURCES", test_sources), \
         patch("app.services.real_data_loader.download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.services.real_data_loader.extract_zip", return_value="/tmp/r.tif") as mock_zip, \
         patch("app.services.real_data_loader.ingest_vector_file", new_callable=AsyncMock) as mock_vec, \
         patch("app.services.real_data_loader.ingest_raster_file", new_callable=AsyncMock) as mock_ras:
         
        # Make download return a path
        mock_dl.return_value = "/tmp/file"
        
        # Run
        await load_real_global_data()
        
        # Verify Download calls
        assert mock_dl.call_count == 2
        
        # Verify Vector Ingestion calls
        # Should be called for levels 1, 2, 3
        assert mock_vec.call_count == 3
        
        # Verify Raster Ingestion calls
        # Should be called once (handle levels internally)
        assert mock_ras.call_count == 1
        
        # Verify args for vector
        # Check first call
        args, kwargs = mock_vec.call_args_list[0]
        assert args[1] == "Test Vector"
        assert kwargs['resolution'] == 1
        
        # Check last call
        args, kwargs = mock_vec.call_args_list[2]
        assert kwargs['resolution'] == 3
