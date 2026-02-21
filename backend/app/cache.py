"""
Redis caching layer for TerraCube IDEAS.

Provides caching for frequently accessed data:
- Topology lookup results
- Viewport cell queries
- DGGAL geometry responses
- Dataset metadata

Cache invalidation strategy:
- TTL-based invalidation for topology/viewport queries
- Manual invalidation on dataset mutations
"""
import json
import logging
from typing import Optional, List, Any, Dict
from datetime import timedelta

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

from app.config import settings

logger = logging.getLogger(__name__)

# Cache key prefixes
CACHE_PREFIX_TOPOLOGY = "dggs:topology:"
CACHE_PREFIX_VIEWPORT = "dggs:viewport:"
CACHE_PREFIX_GEOMETRY = "dggs:geometry:"
CACHE_PREFIX_DATASET = "dggs:dataset:"
CACHE_PREFIX_STATS = "dggs:stats:"

# Default TTL values (seconds)
TTL_TOPOLOGY = 86400  # 24 hours
TTL_VIEWPORT = 300   # 5 minutes
TTL_GEOMETRY = 86400  # 24 hours
TTL_DATASET = 3600  # 1 hour
TTL_STATS = 600  # 10 minutes


class CacheBackend:
    """Base class for cache backends."""

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        raise NotImplementedError

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Set value in cache with TTL."""
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        raise NotImplementedError

    async def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching pattern."""
        raise NotImplementedError

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        raise NotImplementedError


class RedisCache(CacheBackend):
    """Redis-based cache backend."""

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._connected = False

    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            try:
                self._client = await redis.from_url(
                    f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}"
                )
                await self._client.ping()
                self._connected = True
                logger.info(f"Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self._connected = False
                raise
        return self._client

    def _make_key(self, prefix: str, key: str) -> str:
        """Create full cache key with prefix."""
        return f"{prefix}{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self._connected:
            await self._get_client()

        try:
            value = await self._client.get(self._make_key("", key))
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get error for {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Set value in cache with TTL."""
        if not self._connected:
            await self._get_client()

        try:
            serialized = json.dumps(value)
            await self._client.setex(
                self._make_key("", key),
                ttl,
                serialized
            )
        except Exception as e:
            logger.warning(f"Cache set error for {key}: {e}")

    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        if not self._connected:
            await self._get_client()

        try:
            await self._client.delete(self._make_key("", key))
        except Exception as e:
            logger.warning(f"Cache delete error for {key}: {e}")

    async def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching pattern."""
        if not self._connected:
            await self._get_client()

        try:
            pattern = self._make_key("", pattern).replace("*", "")
            keys = []
            async for key in self._client.scan_iter(match=f"{pattern}*"):
                keys.append(key)
            if keys:
                await self._client.delete(*keys)
        except Exception as e:
            logger.warning(f"Cache delete_pattern error for {pattern}: {e}")

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self._connected:
            await self._get_client()

        try:
            return await self._client.exists(self._make_key("", key))
        except Exception as e:
            return False


class MemoryCache(CacheBackend):
    """In-memory cache for development/testing when Redis is unavailable."""

    def __init__(self):
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._ttl_store: Dict[str, float] = {}

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        import time
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                return value
            # Expired
            del self._cache[key]
        return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Set value in cache with TTL."""
        import time
        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        if key in self._cache:
            del self._cache[key]

    async def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching pattern."""
        import fnmatch
        keys_to_delete = [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]
        for key in keys_to_delete:
            del self._cache[key]

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._cache


# Global cache instance (will be initialized on startup)
_cache: Optional[CacheBackend] = None


def get_cache() -> CacheBackend:
    """Get the cache backend instance."""
    global _cache
    if _cache is None:
        if redis:
            _cache = RedisCache()
        else:
            logger.warning("Redis not available, using in-memory cache")
            _cache = MemoryCache()
    return _cache


async def cached_get(prefix: str, key: str, ttl: int) -> Optional[Any]:
    """
    Generic cached get function.

    Args:
        prefix: Cache key prefix
        key: Cache key (without prefix)
        ttl: TTL for cache if creating new entry

    Returns:
        Cached value or None
    """
    cache = get_cache()
    return await cache.get(f"{prefix}{key}")


async def cached_set(prefix: str, key: str, value: Any, ttl: int) -> None:
    """
    Generic cached set function.

    Args:
        prefix: Cache key prefix
        key: Cache key (without prefix)
        value: Value to cache
        ttl: TTL in seconds
    """
    cache = get_cache()
    await cache.set(f"{prefix}{key}", value, ttl)


async def invalidate_dataset(dataset_id: str) -> None:
    """
    Invalidate all cache entries for a dataset.

    Call this when a dataset is created, updated, or deleted.
    """
    import fnmatch

    cache = get_cache()

    # Invalidate viewport cache
    await cache.delete_pattern(f"{CACHE_PREFIX_VIEWPORT}{dataset_id}:*")

    # Invalidate dataset metadata cache
    await cache.delete(f"{CACHE_PREFIX_DATASET}{dataset_id}")

    # Invalidate stats cache
    await cache.delete_pattern(f"{CACHE_PREFIX_STATS}{dataset_id}:*")

    logger.debug(f"Invalidated cache for dataset {dataset_id}")


async def invalidate_topology() -> None:
    """
    Invalidate topology cache.

    Call this if topology is updated (rarely needed).
    """
    cache = get_cache()
    await cache.delete_pattern(f"{CACHE_PREFIX_TOPOLOGY}*")
    logger.debug("Invalidated topology cache")
