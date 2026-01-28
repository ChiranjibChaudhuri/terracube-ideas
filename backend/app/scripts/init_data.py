
import asyncio
import logging
import os
from sqlalchemy import text
from app.db import get_db_pool
from app.services.real_data_loader import load_real_global_data

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MOCK_DATASETS = [
    "Global Regions (Lv2)",
    "Protected Areas (Lv3)",
    "Ocean Bathymetry (Lv4)",
    "Global Temperature (Lv4)",
    "Global Elevation (Lv4)",
    "North America Climate (Lv5)",
    "Europe Climate (Lv5)",
    "South America Elevation (Lv5)",
    # Test datasets created by backend test suite
    "DS_A",
    "DS_B",
    "Poly Test",
    "Vector Test"
]

async def clear_mock_data():
    """Clear simulated/mock datasets."""
    logger.info("Cleaning up mock datasets...")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # We delete by name for safety
        for name in MOCK_DATASETS:
            # Check if exists first to log
            row = await conn.fetchrow("SELECT id FROM datasets WHERE name = $1", name)
            if row:
                logger.info(f"Deleting mock dataset: {name} ({row['id']})")
                # Cascade should handle cell_objects partitions if foreign keys are set UP correctly?
                # Usually partitions need explicit DROP TABLE if not automated. 
                # But creating datasets creates table `cell_objects_<uuid>`.
                # We need to drop those tables.
                
                table_name = f"cell_objects_{str(row['id']).replace('-', '_')}"
                try:
                    await conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
                except Exception as e:
                    logger.warning(f"Failed to drop partition {table_name}: {e}")
                
                await conn.execute("DELETE FROM datasets WHERE id = $1", row['id'])

    logger.info("Mock data cleanup complete.")

async def clear_operation_results():
    """Clear persisted operation result datasets."""
    logger.info("Cleaning up operation result datasets...")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name
            FROM datasets
            WHERE
                metadata->>'source' IN ('spatial_op', 'operation')
                OR metadata->>'source_type' IN ('spatial_op', 'operation')
                OR (metadata->'parents') IS NOT NULL
                OR name ILIKE '% result%'
            """
        )
        for row in rows:
            table_name = f"cell_objects_{str(row['id']).replace('-', '_')}"
            try:
                await conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            except Exception as e:
                logger.warning(f"Failed to drop partition {table_name}: {e}")
            await conn.execute("DELETE FROM datasets WHERE id = $1", row['id'])
            logger.info(f"Deleted operation result dataset: {row['name']} ({row['id']})")
    logger.info("Operation result cleanup complete.")

async def main():
    logger.info("Starting Data Initialization Service...")
    
    # Wait for DB? get_db_pool retries usually? logic inside real_data_loader handles it.
    
    clean_mock = os.getenv("CLEAN_MOCK_DATA", "true").lower() == "true"
    
    if clean_mock:
        try:
            await clear_mock_data()
        except Exception as e:
            logger.error(f"Error cleaning mock data: {e}")

    try:
        await clear_operation_results()
    except Exception as e:
        logger.error(f"Error cleaning operation results: {e}")
    
    try:
        # Load Real Data
        # session is passed as None because real_data_loader uses get_db_pool internally
        await load_real_global_data(None)
    except Exception as e:
        logger.error(f"Error loading real data: {e}")
        # Build should succeed even if data fails? 
        # User said "it will load if data is not there".
        # We should exit 0 or 1? exit 1 restarts if restart policy set?
        # User said "check and load ... everytime docker starts". 
        # If we exit 1, docker might restart loop.
        pass
    
    logger.info("Data Initialization Service Finished.")

if __name__ == "__main__":
    asyncio.run(main())
