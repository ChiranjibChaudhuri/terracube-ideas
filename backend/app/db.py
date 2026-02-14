import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event, text
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Direct asyncpg URL for raw connections if needed
DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    RAW_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
else:
    RAW_DATABASE_URL = DATABASE_URL
# SQLAlchemy async URL
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
elif DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    SQLALCHEMY_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    SQLALCHEMY_DATABASE_URL = DATABASE_URL


# Connection pool metrics tracking
class PoolMetrics:
    """Track connection pool health metrics."""

    def __init__(self):
        self.total_checkouts = 0
        self.failed_checkouts = 0
        self.total_checkins = 0
        self.failed_checkins = 0

    def record_checkout(self, success: bool):
        self.total_checkouts += 1
        if not success:
            self.failed_checkouts += 1

    def record_checkin(self, success: bool):
        self.total_checkins += 1
        if not success:
            self.failed_checkins += 1

    def get_health(self) -> dict:
        """Get current pool health status."""
        return {
            "total_checkouts": self.total_checkouts,
            "failed_checkouts": self.failed_checkouts,
            "total_checkins": self.total_checkins,
            "failed_checkins": self.failed_checkins,
            "checkout_success_rate": 1.0 - (self.failed_checkouts / self.total_checkouts) if self.total_checkouts > 0 else 1.0,
            "checkin_success_rate": 1.0 - (self.failed_checkins / self.total_checkins) if self.total_checkins > 0 else 1.0,
        }


_pool_metrics = PoolMetrics()


@event.listens_for(engine)
def receive_new_connection(dbapi_conn, connection_proxy, connection):
    """Log new connection for monitoring."""
    logger.debug("New database connection established")


@event.listens_for(engine)
def receive_checkout(dbapi_conn, connection_proxy, connection):
    """Track checkout success/failure for metrics."""
    try:
        _pool_metrics.record_checkout(True)
    except Exception:
        pass


@event.listens_for(engine)
def receive_checkout_failure(dbapi_conn, connection_proxy, connection, exception):
    """Track checkout failures for metrics."""
    try:
        _pool_metrics.record_checkout(False)
        logger.warning(f"Connection checkout failure: {exception}")
    except Exception:
        pass


engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=False,  # Disable SQL logging in production
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections are alive
    pool_recycle=3600,  # Recycle connections every hour
    connect_args={
        "options": f"-c statement_timeout={settings.DB_STATEMENT_TIMEOUT}s",
        "server_settings": {"application_name": "terracube_ideas"}
    }
)
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
        _pool = await asyncpg.create_pool(RAW_DATABASE_URL)
    return _pool

async def close_db_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def get_db_health() -> dict:
    """
    Get database connection pool health status.

    Returns:
        Dict with pool metrics and connection status
    """
    from sqlalchemy import text

    health = {
        "status": "unknown",
        "pool_size": engine.pool.size(),
        "pool_checked_in": engine.pool.checkedout(),
        "pool_overflow": engine.pool.overflow(),
        "pool_checked_in_overflow": engine.pool.checkedout_overflow(),
        "metrics": _pool_metrics.get_health()
    }

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            health["status"] = "healthy"
    except Exception as e:
        health["status"] = "unhealthy"
        health["error"] = str(e)

    return health
