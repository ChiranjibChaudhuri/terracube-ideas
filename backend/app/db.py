import asyncpg
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings

# Direct asyncpg URL for raw connections if needed
DATABASE_URL = settings.DATABASE_URL
# SQLAlchemy async URL
SQLALCHEMY_DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://")

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Dependency for FastAPI routers
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Legacy raw pool (to be deprecated or used for heavy bulk ops)
_pool = None

async def get_db_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool

async def close_db_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
