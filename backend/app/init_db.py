import os
import logging
from pathlib import Path
from app.db import get_db_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_db():
    """
    Initialize the database schema.
    The pool is NOT closed here - lifecycle is managed by the application (main.py).
    """
    try:
        pool = await get_db_pool()
        
        # Use path relative to this module for portability
        # In Docker: /app/db/schema.sql, locally: ../db/schema.sql from this file
        schema_path = os.environ.get(
            "DB_SCHEMA_PATH",
            str(Path(__file__).parent.parent / "db" / "schema.sql")
        )
        
        if not os.path.exists(schema_path):
            # Fallback to Docker path
            schema_path = "/app/db/schema.sql"
            
        with open(schema_path, "r") as f:
            schema_sql = f.read()
            
        async with pool.acquire() as conn:
            await conn.execute(schema_sql)
            
        logger.info(f"Database schema initialized from {schema_path}.")
    except Exception as e:
        logger.error(f"Failed to initialize DB: {e}")
        raise


if __name__ == "__main__":
    import asyncio
    from app.db import close_db_pool
    
    async def run():
        await init_db()
        await close_db_pool()
    
    asyncio.run(run())
