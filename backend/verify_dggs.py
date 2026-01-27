
import asyncio
import logging
import sys
import os
from sqlalchemy import text
from app.db import AsyncSessionLocal
from app.dggal_utils import get_dggal_service

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_dggs_levels():
    async with AsyncSessionLocal() as session:
        # Get all datasets
        result = await session.execute(text("SELECT id, name FROM datasets"))
        datasets = result.fetchall()
        
        dgg_service = get_dggal_service()
        
        for ds_id, ds_name in datasets:
            logger.info(f"Checking dataset: {ds_name} ({ds_id})")
            
            # Get all dggids for this dataset
            # We fetch all to be accurate, or we could stream/chunk if too large.
            # For verification, let's fetch first 10000 or count distinct.
            
            # Efficient way: fetch all dggids
            result = await session.execute(text(f"SELECT dggid FROM cell_objects WHERE dataset_id = '{ds_id}'"))
            rows = result.fetchall()
            
            if not rows:
                logger.info(f"  - No cells found.")
                continue
                
            level_counts = {}
            for row in rows:
                dggid = row[0]
                if not dggid: continue
                
                try:
                    level = dgg_service.get_zone_level(dggid)
                    level_counts[level] = level_counts.get(level, 0) + 1
                except Exception as e:
                    logger.warning(f"  - Error getting level for {dggid}: {e}")
            
            # Print report
            logger.info(f"  - Total cells: {len(rows)}")
            sorted_levels = sorted(level_counts.keys())
            for lvl in sorted_levels:
                logger.info(f"  - Level {lvl}: {level_counts[lvl]} cells")
                
            
if __name__ == "__main__":
    # Ensure current directory is in python path for imports
    sys.path.append(os.getcwd())
    asyncio.run(verify_dggs_levels())
