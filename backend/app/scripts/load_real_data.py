
import asyncio
import logging
from app.services.real_data_loader import load_real_global_data
from app.db import close_db_pool

# Set up logging
logging.basicConfig(level=logging.INFO)

async def run_script():
    await load_real_global_data()
    await close_db_pool()

if __name__ == "__main__":
    asyncio.run(run_script())
