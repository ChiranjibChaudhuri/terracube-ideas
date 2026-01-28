
import asyncio
import logging
import sys
import os

# Ensure backend directory is in path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.db import get_db_pool, close_db_pool
from app.dggal_utils import get_dggal_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def populate_topology(dggs_name="IVEA3H", max_level=7):
    logger.info(f"Populating topology for {dggs_name} up to level {max_level}")
    
    try:
        pool = await get_db_pool()
        service = get_dggal_service(dggs_name)
        
        # Global BBox
        bbox = [-90, -180, 90, 180] 
        
        total_inserted = 0
        
        async with pool.acquire() as conn:
            # Clear existing for this run? Or just upsert. 
            # User might want clean start, but upsert is safer.
            # Let's truncate if strictly ensuring correctness, but for now Upsert.
            
            for level in range(1, max_level + 1):
                logger.info(f"Listing zones for level {level}...")
                zones = service.list_zones_bbox(level, bbox)
                logger.info(f"Found {len(zones)} zones at level {level}")
                
                batch_topology = []
                
                # Fetch topology for each zone
                # This might be slow if sequential. We can parallelize extraction slightly?
                # But dggal_utils has a lock.
                # Just sequential loop is safest for WASM stability.
                
                for i, dggid in enumerate(zones):
                    # Neighbors
                    neighbors = service.get_neighbors(dggid)
                    parent = service.get_parent(dggid)
                    
                    if parent:
                        # Add self-parent link? No, schema says parent_dggid column.
                        # Wait, schema: (dggid, neighbor_dggid) PK.
                        # Parent is an attribute of the dggid? 
                        # No, the table primary key is (dggid, neighbor_dggid).
                        # This table seems to mix "Adjacency" and "Hierarchy".
                        # Row: dggid='A', neighbor_dggid='B', parent_dggid='P', level=3
                        # So for each neighbor B of A, we store that P is parent of A. 
                        # This duplicates P info for every neighbor row. A bit denormalized but okay.
                        pass
                        
                    # Insert rows for neighbors
                    for nb in neighbors:
                        batch_topology.append((dggid, nb, parent, level))
                        
                    if len(batch_topology) >= 1000:
                        await _insert_batch(conn, batch_topology)
                        total_inserted += len(batch_topology)
                        batch_topology = []
                        
                    if i % 1000 == 0 and i > 0:
                        logger.info(f"Processed {i}/{len(zones)} zones at level {level}")

                if batch_topology:
                    await _insert_batch(conn, batch_topology)
                    total_inserted += len(batch_topology)
                    
        logger.info(f"Topology population complete. Total rows: {total_inserted}")
        
    except Exception as e:
        logger.error(f"Failed to populate topology: {e}")
        import traceback
        traceback.print_exc()

async def _insert_batch(conn, rows):
    if not rows:
        return
    query = """
        INSERT INTO dgg_topology (dggid, neighbor_dggid, parent_dggid, level)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (dggid, neighbor_dggid) DO NOTHING
    """
    await conn.executemany(query, rows)

if __name__ == "__main__":
    async def run():
        await populate_topology()
        await close_db_pool()
    
    asyncio.run(run())
