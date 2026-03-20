#!/usr/bin/env python3
"""
Database Initialization Script for TerraCube IDEAS

This script performs initial database setup:
1. Creates schema tables (idempotent if they exist)
2. Populates dgg_topology table for spatial operations
3. Creates indexes for performance
4. Runs basic health checks

Usage:
    python -m app.scripts.init_database.py [--levels N] [--dggs IVEA3H]

Environment Variables:
    - TOPOLOGY_LEVELS: Number of DGGS levels to populate (default: 5)
    - TOPOLOGY_DGGS: DGGS system to use (default: IVEA3H)
    - AUTO_POPULATE: Set to 'false' to skip topology population
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure backend directory is in path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))


from app.db import get_db_pool, close_db_pool
from app.dggal_utils import get_dggal_service
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_schema_if_not_exists(conn):
    """
    Create database schema tables.
    This is idempotent - safe to run multiple times.
    """
    logger.info("Ensuring database schema exists...")
    schema_path = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
    schema_sql = schema_path.read_text()
    await conn.execute(schema_sql)
    logger.info("Schema creation complete.")


async def check_topology_populated(conn) -> bool:
    """
    Check if topology table has been populated.
    Returns True if topology has data, False otherwise.
    """
    result = await conn.fetchrow("SELECT COUNT(*) FROM dgg_topology")
    count = result[0] if result else 0
    is_populated = count > 0
    logger.info(f"Topology table has {count} rows. Populated: {is_populated}")
    return is_populated


async def populate_topology(dggs_name: str = "IVEA3H", max_level: int = 5) -> int:
    """
    Populate the dgg_topology table with neighbor and parent relationships.
    This is required for buffer, aggregate, and propagate operations.

    Args:
        dggs_name: DGGS system to use (default: IVEA3H)
        max_level: Maximum resolution level to populate (default: 5)

    Returns:
        Number of topology rows inserted
    """
    logger.info(f"Populating topology for {dggs_name} up to level {max_level}")

    service = get_dggal_service(dggs_name)

    # Global BBox for topology generation
    bbox = [-90, -180, 90, 180]

    total_inserted = 0

    async with await get_db_pool().acquire() as conn:
        # Clear existing topology for clean repopulation
        await conn.execute("DELETE FROM dgg_topology")
        logger.info("Cleared existing topology data")

        for level in range(1, max_level + 1):
            logger.info(f"Listing zones for level {level}...")
            zones = service.list_zones_bbox(level, bbox)
            zone_count = len(zones)
            logger.info(f"Found {zone_count} zones at level {level}")

            if zone_count == 0:
                logger.warning(f"No zones found at level {level}")
                continue

            batch_topology = []
            processed = 0

            # Fetch topology for each zone
            for i, dggid in enumerate(zones):
                try:
                    neighbors = service.get_neighbors(dggid)
                    parent = service.get_parent(dggid)

                    # Insert a row for each neighbor relationship
                    # The topology table stores: (dggid, neighbor_dggid, parent_dggid, level)
                    if neighbors:
                        for nb in neighbors:
                            batch_topology.append((dggid, nb, parent, level))

                    processed += 1

                    # Batch insert every 1000 zones
                    if len(batch_topology) >= 1000:
                        await _insert_batch(conn, batch_topology)
                        total_inserted += len(batch_topology)
                        batch_topology = []
                        logger.info(f"Processed {processed}/{zone_count} zones at level {level}")

                except Exception as e:
                    logger.warning(f"Error processing zone {dggid}: {e}")

            # Insert remaining batch for this level
            if batch_topology:
                await _insert_batch(conn, batch_topology)
                total_inserted += len(batch_topology)
                logger.info(f"Completed level {level}: {processed} zones processed")

        logger.info(f"Topology population complete. Total rows: {total_inserted}")

    return total_inserted


async def _insert_batch(conn, rows):
    """Insert a batch of topology rows with upsert on conflict."""
    if not rows:
        return

    query = """
        INSERT INTO dgg_topology (dggid, neighbor_dggid, parent_dggid, level)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (dggid, neighbor_dggid) DO NOTHING
    """
    await conn.executemany(query, rows)


async def run_health_checks(conn) -> dict:
    """
    Run health checks on database and return status.
    """
    health = {
        "schema": "unknown",
        "topology_populated": False,
        "topology_rows": 0,
        "dataset_count": 0,
        "cell_count": 0,
        "user_count": 0
    }

    # Check tables exist
    tables = await conn.fetch("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name IN ('users', 'datasets', 'cell_objects', 'dgg_topology', 'uploads')
        ORDER BY table_name
    """)

    if tables:
        table_names = [row[0] for row in tables]
        if all(t in table_names for t in ['users', 'datasets', 'cell_objects', 'dgg_topology', 'uploads']):
            health["schema"] = "ok"

    # Check topology
    health["topology_populated"] = await check_topology_populated(conn)
    topo_count = await conn.fetchrow("SELECT COUNT(*) FROM dgg_topology")
    health["topology_rows"] = topo_count[0] if topo_count else 0

    # Check data counts
    dataset_count = await conn.fetchrow("SELECT COUNT(*) FROM datasets")
    health["dataset_count"] = dataset_count[0] if dataset_count else 0

    cell_count = await conn.fetchrow("SELECT COUNT(*) FROM cell_objects")
    health["cell_count"] = cell_count[0] if cell_count else 0

    user_count = await conn.fetchrow("SELECT COUNT(*) FROM users")
    health["user_count"] = user_count[0] if user_count else 0

    return health


async def main():
    """Main initialization routine."""
    logger.info("=" * 60)
    logger.info("TerraCube IDEAS Database Initialization")
    logger.info("=" * 60)

    # Parse command line arguments
    max_level = int(os.getenv("TOPOLOGY_LEVELS", "5"))
    dggs_name = os.getenv("TOPOLOGY_DGGS", "IVEA3H")
    auto_populate = os.getenv("AUTO_POPULATE", "true").lower() != "false"

    # Parse command line args
    import sys
    levels = 5
    dggs = "IVEA3H"

    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--help":
            print("Usage: python init_database.py [--levels N] [--dggs NAME]")
            print("  --levels N: Number of DGGS levels to populate (default: 5)")
            print("  --dggs NAME: DGGS system to use (default: IVEA3H)")
            print()
            print("Environment variables:")
            print("  TOPOLOGY_LEVELS: Number of DGGS levels to populate")
            print("  TOPOLOGY_DGGS: DGGS system to use")
            print("  AUTO_POPULATE: Set to 'false' to skip topology population")
            return
        elif arg.startswith("--levels"):
            levels = int(arg.split("=")[1]) if "=" in arg else 5
        elif arg.startswith("--dggs"):
            dggs = arg.split("=")[1] if "=" in arg else "IVEA3H"

    try:
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            # Step 1: Create schema
            logger.info("Step 1: Creating database schema...")
            await create_schema_if_not_exists(conn)

            # Step 2: Check topology population status
            logger.info("Step 2: Checking topology status...")
            is_populated = await check_topology_populated(conn)

            # Step 3: Populate topology if needed
            if not is_populated and auto_populate:
                logger.info(f"Step 3: Populating topology (levels: {levels}, DGGS: {dggs})...")
                rows = await populate_topology(dggs, levels)
                logger.info(f"Topology population complete: {rows} rows inserted")
            else:
                if is_populated:
                    logger.info("Step 3: Topology already populated, skipping...")
                else:
                    logger.info("Step 3: Auto-populate disabled, skipping topology...")

            # Step 4: Run health checks
            logger.info("Step 4: Running health checks...")
            health = await run_health_checks(conn)

            logger.info("")
            logger.info("=" * 60)
            logger.info("Database Initialization Complete")
            logger.info("=" * 60)
            logger.info(f"Schema Status: {health['schema']}")
            logger.info(f"Topology Populated: {health['topology_populated']}")
            logger.info(f"Topology Rows: {health['topology_rows']}")
            logger.info(f"Datasets: {health['dataset_count']}")
            logger.info(f"Cells: {health['cell_count']}")
            logger.info(f"Users: {health['user_count']}")

            # Warn if topology not populated
            if not health["topology_populated"]:
                logger.warning("")
                logger.warning("!" * 60)
                logger.warning("WARNING: Topology table is empty!")
                logger.warning("Spatial operations (buffer, aggregate, propagate) will NOT work.")
                logger.warning(f"Run: python -m app.scripts.init_database.py --levels {levels}")
                logger.warning("!" * 60)

    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        await close_db_pool()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
