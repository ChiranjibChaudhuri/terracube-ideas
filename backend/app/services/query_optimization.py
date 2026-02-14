"""
Query Optimization Service for TerraCube IDEAS

Provides materialized view management and query caching
to optimize common DGGS query patterns.
"""

import asyncio
from typing import List, Optional, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db_pool
import logging

logger = logging.getLogger(__name__)


class QueryOptimizationService:
    """
    Manages materialized views and query caching for performance.

    Features:
    1. Materialized views for cell lookup by viewport
    2. Pre-aggregated dataset views for fast zoom
    3. Index management and recommendations
    4. Query result caching
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes

    async def create_materialized_view(
        self,
        dataset_id: str,
        view_name: Optional[str] = None
        refresh: bool = False
    ) -> str:
        """
        Create a materialized view for a dataset's cell_objects.

        Materialized views store pre-computed results and automatically refresh,
        providing significantly faster queries for common access patterns.

        Args:
            dataset_id: Dataset to materialize
            view_name: Optional custom view name (default: mv_cells_{dataset_id})
            refresh: Whether to refresh existing data

        Returns:
            Name of created materialized view
        """
        from app.models import Dataset, CellObject
        import uuid

        try:
            ds_uuid = uuid.UUID(dataset_id)
        except ValueError:
            raise ValueError(f"Invalid dataset_id: {dataset_id}")

        # Check if dataset exists
        ds = await self.db.get(select(Dataset).where(Dataset.id == ds_uuid))
        if not ds:
            raise ValueError(f"Dataset not found: {dataset_id}")

        view_name = view_name or f"mv_cells_{dataset_id}"

        # Drop existing view if refreshing
        if refresh:
            try:
                await self.db.execute(text(f'DROP MATERIALIZED VIEW IF EXISTS {view_name}'))
                logger.info(f"Dropped materialized view {view_name} for refresh")
            except Exception:
                pass  # Ignore if doesn't exist

        # Create materialized view
        await self.db.execute(text(f"""
            CREATE MATERIALIZED VIEW {view_name} AS
            SELECT
                id, dataset_id, dggid, tid, attr_key, value_text, value_num, value_json, created_at
            FROM cell_objects
            WHERE dataset_id = :dataset_id
            WITH DATA;

            CREATE UNIQUE INDEX idx_{view_name}_dggid ON {view_name} (dggid);
            CREATE INDEX idx_{view_name}_tid ON {view_name} (tid);
            CREATE INDEX idx_{view_name}_attr_key ON {view_name} (attr_key);
            CREATE INDEX idx_{view_name}_dataset_id ON {view_name} (dataset_id);
        """), {"dataset_id": ds_uuid})

        logger.info(f"Created materialized view {view_name} for dataset {dataset_id}")

        # Grant necessary permissions
        await self.db.execute(text(f"GRANT SELECT ON {view_name} TO PUBLIC;"))

        return view_name

    async def create_aggregated_view(
        self,
        source_dataset_id: str,
        target_level: int,
        agg_method: str = "mean",
        view_name: Optional[str] = None
    ) -> str:
        """
        Create a materialized view with pre-aggregated data at a coarser level.

        This enables fast zooming without on-the-fly aggregation.
        """
        from app.models import Dataset, CellObject
        from app.dggal_utils import get_dggal_service
        import uuid

        try:
            source_uuid = uuid.UUID(source_dataset_id)
        except ValueError:
            raise ValueError(f"Invalid source dataset_id: {source_dataset_id}")

        # Get source dataset
        source_ds = await self.db.get(select(Dataset).where(Dataset.id == source_uuid))
        if not source_ds:
            raise ValueError(f"Source dataset not found: {source_dataset_id}")

        # Get target level from source
        source_level = source_ds.level or 0
        if target_level >= source_level:
            raise ValueError(f"Target level {target_level} must be coarser than source level {source_level}")

        view_name = view_name or f"mv_agg_{source_dataset_id}_L{target_level}_{agg_method}"

        # Drop existing view
        try:
            await self.db.execute(text(f'DROP MATERIALIZED VIEW IF EXISTS {view_name}'))
        except Exception:
            pass  # Ignore if doesn't exist

        # Get DGGS service for parent lookups
        dggs = get_dggal_service(source_ds.dggs_name or "IVEA3H")

        # Build aggregation SQL based on method
        if agg_method == "mean":
            agg_func = "AVG(child.value_num)"
        elif agg_method == "sum":
            agg_func = "SUM(child.value_num)"
        elif agg_method == "min":
            agg_func = "MIN(child.value_num)"
        elif agg_method == "max":
            agg_func = "MAX(child.value_num)"
        elif agg_method == "count":
            agg_func = "COUNT(child.value_num)"
        elif agg_method == "mode":
            # Most frequent value (mode)
            agg_func = "MODE() WITHIN ORDER BY (child.value_num) DESC, LIMIT 1) AS mode_val"
        else:
            raise ValueError(f"Unsupported aggregation method: {agg_method}")

        # Create materialized aggregated view
        await self.db.execute(text(f"""
            CREATE MATERIALIZED VIEW {view_name} AS
            SELECT
                parent.dggid, 0, a.attr_key,
                {agg_func}, NULL, NULL, NULL,
                child.created_at
            FROM (
                SELECT
                    child.dggid, child.tid, child.attr_key, child.value_num, child.value_text, child.value_json, child.created_at
                FROM cell_objects child
                INNER JOIN dgg_topology parent ON child.dggid = parent.parent_dggid
                WHERE child.dataset_id = :source_id
                    AND parent.level = :target_level
            ) AS parent
            INNER JOIN LATERAL (
                SELECT parent.dggid, COUNT(*) OVER (PARTITION BY parent.dggid) as cell_count
                FROM parent
            ) AS stats ON parent.dggid = stats.dggid
            WITH DATA;

            CREATE UNIQUE INDEX idx_{view_name}_dggid ON {view_name} (dggid);
            CREATE INDEX idx_{view_name}_attr_key ON {view_name} (attr_key);
        """), {
            "source_dataset_id": source_uuid,
            "target_level": target_level,
            "agg_method": agg_method
        })

        logger.info(f"Created aggregated view {view_name}: source {source_uuid} L{source_level} -> {target_level} ({agg_method})")

        return view_name

    async def get_query_plan(
        self,
        sql: str
    ) -> Dict[str, Any]:
        """
        Get query execution plan from PostgreSQL EXPLAIN.

        Useful for analyzing and optimizing slow queries.
        """
        try:
            result = await self.db.execute(text(f"EXPLAIN (ANALYZE, BUFFERS) {sql}"))
            plan = [dict(row) for row in result]
            return {
                "sql": sql,
                "plan": plan,
                "cost": sum(row.get("total_cost", 0) for row in plan if row.get("total_cost"))
            }
        except Exception as e:
            logger.error(f"Query plan failed: {e}")
            return {
                "sql": sql,
                "error": str(e)
            }

    async def analyze_dataset_queries(
        self,
        dataset_id: str
    ) -> Dict[str, Any]:
        """
        Analyze query patterns and performance for a dataset.

        Returns recommendations for optimization.
        """
        from app.models import Dataset, CellObject
        import uuid

        try:
            ds_uuid = uuid.UUID(dataset_id)
        except ValueError:
            raise ValueError(f"Invalid dataset_id: {dataset_id}")

        # Get dataset info
        ds = await self.db.get(select(Dataset).where(Dataset.id == ds_uuid))
        if not ds:
            raise ValueError(f"Dataset not found: {dataset_id}")

        # Get cell count
        count_result = await self.db.execute(
            select(text("COUNT(*)")).where(CellObject.dataset_id == ds_uuid)
        )
        cell_count = count_result.scalar() or 0

        # Check for existing materialized views
        views_result = await self.db.execute(text("""
            SELECT schemaname, matviewname
            FROM pg_matviews
            WHERE schemaname = 'public'
                AND matviewname LIKE :pattern
        """), {"pattern": f"mv_cells_{ds_uuid}%"})

        has_materialized = views_result.rowcount() > 0

        # Get index information
        indexes_result = await self.db.execute(text("""
            SELECT
                indexname,
                attname,
                n_distinct,
                idx_scan
            FROM pg_indexes
            WHERE schemaname = 'public'
                AND tablename = 'cell_objects'
        """))

        indexes = []
        index_count = 0
        missing_indexes = []

        for row in indexes_result:
            indexes.append({
                "name": row[0],
                "column": row[1],
                "unique": row[2],
                "scans": row[3]
            })
            index_count += 1

        # Check for recommended indexes
        if not any(idx["column"] == "dggid" for idx in indexes):
            missing_indexes.append("dggid")

        if not any(idx["column"] == "attr_key" for idx in indexes):
            missing_indexes.append("attr_key")

        if index_count == 0:
            missing_indexes.append("dataset_id")

        return {
            "dataset_id": dataset_id,
            "cell_count": cell_count,
            "has_materialized_view": has_materialized,
            "index_count": index_count,
            "indexes": indexes,
            "missing_indexes": missing_indexes,
            "recommendations": []
        }

    async def optimize_dataset(
        self,
        dataset_id: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Apply optimizations to a dataset:
        1. Create materialized view
        2. Create recommended indexes

        Args:
            dataset_id: Dataset to optimize
            force: Force optimization even if already materialized

        Returns:
            Optimization results with actions taken
        """
        results = {
            "dataset_id": dataset_id,
            "actions_taken": []
        }

        # Analyze current state
        analysis = await self.analyze_dataset_queries(dataset_id)

        # Create materialized view if not exists
        if not analysis["has_materialized_view"] or force:
            view_name = await self.create_materialized_view(dataset_id)
            if view_name:
                results["actions_taken"].append(f"Created materialized view: {view_name}")
                results["materialized_view"] = view_name

        # Create missing indexes
        if analysis["missing_indexes"]:
            # Check if table is large enough to justify indexes
            if analysis["cell_count"] > 10000:  # 10k+ cells
                for index_name in ["dggid", "attr_key", "dataset_id"]:
                    await self.db.execute(text(f"""
                        CREATE INDEX IF NOT EXISTS idx_cell_objects_{dataset_id}_{index_name}
                        ON cell_objects (dataset_id, {index_name})
                    """))
                    results["actions_taken"].append(f"Created index: {index_name}")

        # Update dataset metadata with optimization flags
        from app.models import Dataset
        metadata = analysis.get("recommendations", {})
        if metadata:
            # Store optimization timestamp
            import datetime
            metadata["optimized_at"] = datetime.datetime.now().isoformat()
            results["metadata"] = metadata

        return results


# Singleton instance
_opt_service = None

def get_optimization_service(db: AsyncSession) -> QueryOptimizationService:
    """Get or create singleton QueryOptimizationService instance."""
    global _opt_service
    if _opt_service is None:
        _opt_service = QueryOptimizationService(db)
    return _opt_service
