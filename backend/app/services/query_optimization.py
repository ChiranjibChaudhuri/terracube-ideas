"""
Query Optimization Service for TerraCube IDEAS

Provides materialized view management and query caching
to optimize common DGGS query patterns.
"""

import re
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Dataset, CellObject
import logging

logger = logging.getLogger(__name__)


def _sanitize_identifier(raw: str) -> str:
    """Sanitize a string for use as a SQL identifier (view/index name).
    Only allows alphanumeric and underscores."""
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', raw)
    if not sanitized or not sanitized[0].isalpha():
        sanitized = "v_" + sanitized
    return sanitized[:128]


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
        view_name: Optional[str] = None,
        refresh: bool = False
    ) -> str:
        """
        Create a materialized view for a dataset's cell_objects.

        Args:
            dataset_id: Dataset to materialize
            view_name: Optional custom view name (default: mv_cells_{dataset_id})
            refresh: Whether to refresh existing data

        Returns:
            Name of created materialized view
        """
        import uuid

        try:
            ds_uuid = uuid.UUID(dataset_id)
        except ValueError:
            raise ValueError(f"Invalid dataset_id: {dataset_id}")

        # Check if dataset exists
        result = await self.db.execute(select(Dataset).where(Dataset.id == ds_uuid))
        ds = result.scalars().first()
        if not ds:
            raise ValueError(f"Dataset not found: {dataset_id}")

        # Sanitize view name for SQL identifier safety
        safe_id = str(ds_uuid).replace("-", "_")
        view_name = _sanitize_identifier(view_name) if view_name else f"mv_cells_{safe_id}"

        # Drop existing view if refreshing
        if refresh:
            try:
                await self.db.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}"))
                logger.info(f"Dropped materialized view {view_name} for refresh")
            except Exception:
                pass

        # Create materialized view
        await self.db.execute(text(f"""
            CREATE MATERIALIZED VIEW {view_name} AS
            SELECT
                id, dataset_id, dggid, tid, attr_key, value_text, value_num, value_json, created_at
            FROM cell_objects
            WHERE dataset_id = :dataset_id
            WITH DATA
        """), {"dataset_id": str(ds_uuid)})

        # Create indexes separately (can't mix DDL with params in one statement)
        await self.db.execute(text(
            f"CREATE INDEX IF NOT EXISTS idx_{view_name}_dggid ON {view_name} (dggid)"
        ))
        await self.db.execute(text(
            f"CREATE INDEX IF NOT EXISTS idx_{view_name}_tid ON {view_name} (tid)"
        ))
        await self.db.execute(text(
            f"CREATE INDEX IF NOT EXISTS idx_{view_name}_attr_key ON {view_name} (attr_key)"
        ))

        logger.info(f"Created materialized view {view_name} for dataset {dataset_id}")
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
        """
        import uuid

        try:
            source_uuid = uuid.UUID(source_dataset_id)
        except ValueError:
            raise ValueError(f"Invalid source dataset_id: {source_dataset_id}")

        # Get source dataset
        result = await self.db.execute(select(Dataset).where(Dataset.id == source_uuid))
        source_ds = result.scalars().first()
        if not source_ds:
            raise ValueError(f"Source dataset not found: {source_dataset_id}")

        source_level = source_ds.level or 0
        if target_level >= source_level:
            raise ValueError(f"Target level {target_level} must be coarser than source level {source_level}")

        # Sanitize and build view name
        safe_id = str(source_uuid).replace("-", "_")
        view_name = _sanitize_identifier(view_name) if view_name else f"mv_agg_{safe_id}_L{target_level}_{agg_method}"

        # Drop existing view
        try:
            await self.db.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}"))
        except Exception:
            pass

        # Build aggregation SQL based on method (whitelist approach)
        agg_funcs = {
            "mean": "AVG",
            "sum": "SUM",
            "min": "MIN",
            "max": "MAX",
            "count": "COUNT",
        }

        if agg_method not in agg_funcs:
            raise ValueError(f"Unsupported aggregation method: {agg_method}. Must be one of {list(agg_funcs.keys())}")

        sql_func = agg_funcs[agg_method]

        # Create materialized aggregated view using topology parent lookup
        await self.db.execute(text(f"""
            CREATE MATERIALIZED VIEW {view_name} AS
            SELECT
                t.parent_dggid AS dggid,
                0 AS tid,
                c.attr_key,
                {sql_func}(c.value_num) AS value_num,
                NULL::text AS value_text,
                NULL::jsonb AS value_json
            FROM cell_objects c
            JOIN dgg_topology t ON c.dggid = t.dggid
            WHERE c.dataset_id = :source_id
                AND t.parent_dggid IS NOT NULL
                AND c.value_num IS NOT NULL
            GROUP BY t.parent_dggid, c.attr_key
            WITH DATA
        """), {"source_id": str(source_uuid)})

        await self.db.execute(text(
            f"CREATE INDEX IF NOT EXISTS idx_{view_name}_dggid ON {view_name} (dggid)"
        ))
        await self.db.execute(text(
            f"CREATE INDEX IF NOT EXISTS idx_{view_name}_attr_key ON {view_name} (attr_key)"
        ))

        logger.info(f"Created aggregated view {view_name}: source {source_uuid} L{source_level} -> {target_level} ({agg_method})")
        return view_name

    async def get_query_plan(
        self,
        sql: str
    ) -> Dict[str, Any]:
        """
        Get query execution plan from PostgreSQL EXPLAIN.
        Only allows simple SELECT statements for safety.
        """
        # Security: strict validation - only allow SELECT, reject semicolons and multi-statements
        stripped = sql.strip()
        if not stripped.upper().startswith("SELECT"):
            raise ValueError("EXPLAIN is only supported for SELECT statements")
        if ";" in stripped:
            raise ValueError("Multi-statement queries are not allowed")

        # Additional safety: reject DDL/DML keywords that shouldn't appear in a SELECT
        forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE"]
        upper_sql = stripped.upper()
        for keyword in forbidden:
            # Check for keyword as a standalone word (not inside a string literal)
            if f" {keyword} " in f" {upper_sql} ":
                raise ValueError(f"Forbidden keyword in query: {keyword}")

        try:
            result = await self.db.execute(text(f"EXPLAIN (FORMAT JSON) {stripped}"))
            plan = [dict(row._mapping) for row in result]
            return {
                "sql": sql,
                "plan": plan
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
        import uuid

        try:
            ds_uuid = uuid.UUID(dataset_id)
        except ValueError:
            raise ValueError(f"Invalid dataset_id: {dataset_id}")

        # Get dataset info
        result = await self.db.execute(select(Dataset).where(Dataset.id == ds_uuid))
        ds = result.scalars().first()
        if not ds:
            raise ValueError(f"Dataset not found: {dataset_id}")

        # Get cell count using proper SQLAlchemy
        count_result = await self.db.execute(
            select(func.count()).select_from(CellObject).where(CellObject.dataset_id == ds_uuid)
        )
        cell_count = count_result.scalar() or 0

        # Check for existing materialized views
        safe_pattern = f"mv_cells_{str(ds_uuid).replace('-', '_')}%"
        views_result = await self.db.execute(text("""
            SELECT schemaname, matviewname
            FROM pg_matviews
            WHERE schemaname = 'public'
                AND matviewname LIKE :pattern
        """), {"pattern": safe_pattern})

        has_materialized = views_result.rowcount > 0

        # Get index information
        indexes_result = await self.db.execute(text("""
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
                AND tablename = 'cell_objects'
        """))

        indexes = []
        for row in indexes_result:
            indexes.append({"name": row[0]})

        return {
            "dataset_id": dataset_id,
            "cell_count": cell_count,
            "has_materialized_view": has_materialized,
            "index_count": len(indexes),
            "indexes": indexes,
            "recommendations": []
        }

    async def optimize_dataset(
        self,
        dataset_id: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Apply optimizations to a dataset.
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

        return results


def get_optimization_service(db: AsyncSession) -> QueryOptimizationService:
    """Create a QueryOptimizationService instance for the given session."""
    return QueryOptimizationService(db)
