import asyncio
import logging
from datetime import timedelta
from typing import Iterable

from app.db import get_db_pool

logger = logging.getLogger(__name__)


async def _drop_partitions(conn, dataset_ids: Iterable[str]) -> None:
    for dataset_id in dataset_ids:
        table_name = f"cell_objects_{dataset_id.replace('-', '_')}"
        await conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')


async def cleanup_operation_results(ttl_hours: int) -> int:
    if ttl_hours <= 0:
        return 0

    pool = await get_db_pool()
    interval = f"{ttl_hours} hours"

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id
            FROM datasets
            WHERE created_at < (NOW() - $1::interval)
              AND (
                metadata->>'source' = 'spatial_op'
                OR metadata->>'source_type' = 'spatial_op'
                OR metadata->>'source' = 'operation'
                OR metadata->>'source_type' = 'operation'
              )
            """,
            interval,
        )
        if not rows:
            return 0

        dataset_ids = [str(row['id']) for row in rows]
        await _drop_partitions(conn, dataset_ids)
        await conn.execute("DELETE FROM datasets WHERE id = ANY($1::uuid[])", dataset_ids)
        return len(dataset_ids)


async def run_result_cleanup_loop(ttl_hours: int, interval_minutes: int) -> None:
    if ttl_hours <= 0:
        logger.info("Result cleanup disabled (RESULT_TTL_HOURS <= 0).")
        return

    sleep_seconds = max(interval_minutes, 5) * 60
    while True:
        try:
            removed = await cleanup_operation_results(ttl_hours)
            if removed:
                logger.info(f"Cleaned up {removed} expired operation result datasets.")
        except Exception as exc:
            logger.warning(f"Result cleanup failed: {exc}")
        await asyncio.sleep(sleep_seconds)
