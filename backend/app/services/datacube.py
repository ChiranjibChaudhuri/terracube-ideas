"""
Data Cube Service for Multi-Resolution DGGS Datasets

This service implements automatic aggregation and resolution pyramid management
for DGGS datasets, enabling fast zoom-based queries without on-the-fly computation.
"""

import asyncio
from typing import List, Optional, Dict, Any
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db_pool
from app.dggal_utils import get_dggal_service
import logging

logger = logging.getLogger(__name__)


class DataCubeService:
    """
    Manages multi-resolution DGGS datasets with automatic aggregation.

    When zooming out (coarsening resolution), automatically:
    1. Queries parent cells
    2. Aggregates values (mean, sum, min, max, count)
    3. Returns aggregated layer for visualization

    Also manages materialized views for common query patterns.
    """

    def __init__(self, db: AsyncSession, dggs_name: str = "IVEA3H"):
        self.db = db
        self.dggs = get_dggal_service(dggs_name)

    async def create_aggregated_dataset(
        self,
        source_dataset_id: str,
        target_level: int,
        agg_method: str = "mean",
        name_suffix: str = ""
    ) -> str:
        """
        Create a new dataset by aggregating source dataset to target level.

        Args:
            source_dataset_id: Source dataset to aggregate
            target_level: Target resolution level (must be coarser than source)
            agg_method: Aggregation method (mean, sum, min, max, count, mode)
            name_suffix: Optional suffix for result dataset name

        Returns:
            New dataset ID
        """
        from app.models import Dataset
        import uuid

        # Get source dataset metadata
        import uuid as uuid_mod
        try:
            source_uuid = uuid_mod.UUID(source_dataset_id) if isinstance(source_dataset_id, str) else source_dataset_id
        except ValueError:
            raise ValueError(f"Invalid source dataset ID: {source_dataset_id}")

        result = await self.db.execute(select(Dataset).where(Dataset.id == source_uuid))
        source_ds = result.scalars().first()
        if not source_ds:
            raise ValueError(f"Source dataset not found: {source_dataset_id}")

        # Validate target_level is coarser
        if target_level >= (source_ds.level or 10):
            raise ValueError(f"Target level {target_level} must be coarser than source level {source_ds.level}")

        agg_method = agg_method.lower()
        valid_methods = {"mean", "sum", "min", "max", "count", "mode"}
        if agg_method not in valid_methods:
            raise ValueError(f"Invalid aggregation method: {agg_method}. Must be one of {valid_methods}")

        # Create result dataset
        new_id = uuid.uuid4()
        agg_name = f"{agg_method.capitalize()}{name_suffix}"
        new_dataset = Dataset(
            id=new_id,
            name=f"{source_ds.name} ({agg_name} L{target_level})",
            description=f"Aggregated from {source_ds.name} at level {target_level}",
            dggs_name=source_ds.dggs_name,
            level=target_level,
            metadata_={
                "source": "datacube_aggregation",
                "type": agg_method,
                "parent_dataset": str(source_dataset_id),
                "source_level": source_ds.level,
                "agg_method": agg_method
            },
            status="processing"
        )

        self.db.add(new_dataset)

        # Perform aggregation
        try:
            await self._aggregate_dataset(
                source_dataset_id,
                new_id,
                source_ds.level,
                target_level,
                agg_method
            )

            # Update status
            new_dataset.status = "active"
            await self.db.execute(
                text("UPDATE datasets SET status = :status WHERE id = :id"),
                {"status": "active", "id": str(new_id)}
            )
            await self.db.commit()

            logger.info(f"Created aggregated dataset {new_id} using {agg_method}")
            return str(new_id)

        except Exception as e:
            await self.db.rollback()
            await self.db.execute(
                text("DELETE FROM datasets WHERE id = :id"),
                {"id": str(new_id)}
            )
            await self.db.commit()
            raise e

    async def _aggregate_dataset(
        self,
        source_dataset_id: str,
        target_dataset_id: str,
        source_level: int,
        target_level: int,
        agg_method: str
    ):
        """
        Perform aggregation from source to target level.

        This involves:
        1. Get all cells from source dataset
        2. For each cell, get parent at target level
        3. Group by parent cell and aggregate values
        4. Insert aggregated results
        """
        from app.models import CellObject

        # Map source cells to parent level
        # SQL: Get parent for each dggid, group by parent, aggregate
        if agg_method == "mean":
            agg_sql = text("""
                INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
                SELECT :target_id, t.parent_dggid, 0, a.attr_key,
                       AVG(a.value_num), NULL, NULL
                FROM cell_objects a
                JOIN dgg_topology t ON a.dggid = t.dggid
                WHERE a.dataset_id = :source_id
                AND t.level = :target_level
                AND a.value_num IS NOT NULL
                GROUP BY t.parent_dggid, a.attr_key
                ON CONFLICT (dataset_id, dggid, tid, attr_key) DO UPDATE SET
                    value_num = EXCLUDED.value_num,
                    value_text = EXCLUDED.value_text,
                    value_json = EXCLUDED.value_json
            """)
        elif agg_method == "sum":
            agg_sql = text("""
                INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
                SELECT :target_id, t.parent_dggid, 0, a.attr_key,
                       SUM(a.value_num), NULL, NULL
                FROM cell_objects a
                JOIN dgg_topology t ON a.dggid = t.dggid
                WHERE a.dataset_id = :source_id
                AND t.level = :target_level
                AND a.value_num IS NOT NULL
                GROUP BY t.parent_dggid, a.attr_key
                ON CONFLICT (dataset_id, dggid, tid, attr_key) DO UPDATE SET
                    value_num = EXCLUDED.value_num,
                    value_text = EXCLUDED.value_text,
                    value_json = EXCLUDED.value_json
            """)
        elif agg_method == "min":
            agg_sql = text("""
                INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
                SELECT :target_id, t.parent_dggid, 0, a.attr_key,
                       MIN(a.value_num), NULL, NULL
                FROM cell_objects a
                JOIN dgg_topology t ON a.dggid = t.dggid
                WHERE a.dataset_id = :source_id
                AND t.level = :target_level
                AND a.value_num IS NOT NULL
                GROUP BY t.parent_dggid, a.attr_key
                ON CONFLICT (dataset_id, dggid, tid, attr_key) DO UPDATE SET
                    value_num = EXCLUDED.value_num,
                    value_text = EXCLUDED.value_text,
                    value_json = EXCLUDED.value_json
            """)
        elif agg_method == "max":
            agg_sql = text("""
                INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
                SELECT :target_id, t.parent_dggid, 0, a.attr_key,
                       MAX(a.value_num), NULL, NULL
                FROM cell_objects a
                JOIN dgg_topology t ON a.dggid = t.dggid
                WHERE a.dataset_id = :source_id
                AND t.level = :target_level
                AND a.value_num IS NOT NULL
                GROUP BY t.parent_dggid, a.attr_key
                ON CONFLICT (dataset_id, dggid, tid, attr_key) DO UPDATE SET
                    value_num = EXCLUDED.value_num,
                    value_text = EXCLUDED.value_text,
                    value_json = EXCLUDED.value_json
            """)
        elif agg_method == "count":
            agg_sql = text("""
                INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
                SELECT :target_id, t.parent_dggid, 0, a.attr_key,
                       COUNT(a.value_num), NULL, NULL
                FROM cell_objects a
                JOIN dgg_topology t ON a.dggid = t.dggid
                WHERE a.dataset_id = :source_id
                AND t.level = :target_level
                GROUP BY t.parent_dggid, a.attr_key
                ON CONFLICT (dataset_id, dggid, tid, attr_key) DO UPDATE SET
                    value_num = EXCLUDED.value_num,
                    value_text = EXCLUDED.value_text,
                    value_json = EXCLUDED.value_json
            """)
        elif agg_method == "mode":
            # Find most common value (mode)
            agg_sql = text("""
                WITH counts AS (
                    SELECT a.dggid, a.attr_key, a.value_text, COUNT(*) as count
                    FROM cell_objects a
                    JOIN dgg_topology t ON a.dggid = t.dggid
                    WHERE a.dataset_id = :source_id
                    AND t.level = :target_level
                    GROUP BY a.dggid, a.attr_key, a.value_text
                )
                INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
                SELECT :target_id, c.dggid, 0, c.attr_key,
                       NULL, c.value_text, NULL
                FROM counts c
                WHERE c.count = (
                    SELECT MAX(count)
                    FROM counts
                )
                ON CONFLICT (dataset_id, dggid, tid, attr_key) DO UPDATE SET
                    value_text = EXCLUDED.value_text
            """)

        await self.db.execute(agg_sql, {
            "target_id": target_dataset_id,
            "source_id": source_dataset_id,
            "target_level": target_level
        })

        logger.info(f"Aggregated {source_dataset_id} to {target_dataset_id} using {agg_method}")

    async def get_resolution_pyramid(
        self,
        dataset_id: str,
        base_level: int,
        max_levels: int
    ) -> Dict[int, str]:
        """
        Build a resolution pyramid for fast zooming.

        Returns a mapping of level -> dataset_id for each aggregated level.
        Allows frontend to query directly at target resolution.
        """
        from app.models import Dataset
        import uuid

        # Get source dataset
        import uuid as uuid_mod
        try:
            ds_uuid = uuid_mod.UUID(dataset_id) if isinstance(dataset_id, str) else dataset_id
        except ValueError:
            raise ValueError(f"Invalid dataset ID: {dataset_id}")

        ds_result = await self.db.execute(select(Dataset).where(Dataset.id == ds_uuid))
        source_ds = ds_result.scalars().first()
        if not source_ds:
            raise ValueError(f"Dataset not found: {dataset_id}")

        result = {}
        current_id = dataset_id

        # Create aggregated datasets for each coarser level
        for level_delta in range(1, max_levels + 1):
            target_level = base_level - level_delta
            if target_level < 1:
                break  # Don't go above root

            try:
                agg_id = await self.create_aggregated_dataset(
                    source_dataset_id=current_id,
                    target_level=target_level,
                    agg_method="mean",
                    name_suffix=f"pyramid{level_delta}"
                )
                result[target_level] = agg_id
                current_id = agg_id  # Chain aggregations
                logger.info(f"Created pyramid level {target_level}: {agg_id}")

            except Exception as e:
                logger.warning(f"Failed to create pyramid level {target_level}: {e}")
                break  # Stop on failure

        return result

    async def precompute_views_for_dataset(self, dataset_id: str) -> List[str]:
        """
        Create materialized views for common query patterns on a dataset.

        This significantly speeds up repeated queries like:
        - Cell lookup by viewport dggid list
        - Attribute queries with filters
        """
        from app.models import Dataset
        import uuid

        # Get dataset info
        import uuid as uuid_mod
        import re

        try:
            ds_uuid = uuid_mod.UUID(dataset_id) if isinstance(dataset_id, str) else dataset_id
        except ValueError:
            raise ValueError(f"Invalid dataset ID: {dataset_id}")

        ds_result = await self.db.execute(select(Dataset).where(Dataset.id == ds_uuid))
        ds = ds_result.scalars().first()
        if not ds:
            raise ValueError(f"Dataset not found: {dataset_id}")

        view_names = []

        # Sanitize dataset_id for use in identifiers (only allow hex and hyphens from UUID)
        safe_id = str(ds_uuid).replace("-", "_")
        if not re.match(r'^[a-f0-9_]+$', safe_id):
            raise ValueError(f"Invalid dataset ID for view name: {dataset_id}")

        mv_name = f"mv_cells_{safe_id}"
        try:
            await self.db.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {mv_name}"))
            await self.db.commit()

            # Create materialized view
            await self.db.execute(text(f"""
                CREATE MATERIALIZED VIEW {mv_name} AS
                SELECT id, dataset_id, dggid, tid, attr_key, value_text, value_num, value_json, created_at
                FROM cell_objects
                WHERE dataset_id = :dataset_id
            """), {"dataset_id": str(ds_uuid)})

            # Create index for common query pattern (dggid lookup)
            await self.db.execute(text(f"""
                CREATE INDEX IF NOT EXISTS idx_{mv_name}_dggid ON {mv_name}(dggid);
                CREATE INDEX IF NOT EXISTS idx_{mv_name}_attr_key ON {mv_name}(attr_key);
                CREATE INDEX IF NOT EXISTS idx_{mv_name}_tid ON {mv_name}(tid);
            """))

            await self.db.commit()
            view_names.append(mv_name)
            logger.info(f"Created materialized view {mv_name}")

        except Exception as e:
            logger.warning(f"Failed to create materialized view: {e}")

        return view_names

    async def get_optimized_layer_config(
        self,
        dataset_id: str
    ) -> Dict[str, Any]:
        """
        Return optimized layer configuration for frontend.

        Includes available aggregated levels and precomputed views.
        """
        from app.models import Dataset

        import uuid as uuid_mod
        try:
            ds_uuid = uuid_mod.UUID(dataset_id) if isinstance(dataset_id, str) else dataset_id
        except ValueError:
            return {}

        ds_result = await self.db.execute(select(Dataset).where(Dataset.id == ds_uuid))
        ds = ds_result.scalars().first()
        if not ds:
            return {}

        # Check for precomputed pyramid
        pyramid = {}
        meta = getattr(ds, 'metadata_', None) or {}
        if isinstance(meta, dict):
            pyramid = meta.get("resolution_pyramid", {})

        # Check for materialized views
        views = meta.get("materialized_views", []) if isinstance(meta, dict) else []

        return {
            "dataset_id": str(ds.id),
            "name": ds.name,
            "level": ds.level,
            "dggs_name": ds.dggs_name,
            "resolution_pyramid": pyramid,
            "has_optimized_views": len(views) > 0
        }


def get_datacube_service(db: AsyncSession, dggs_name: str = "IVEA3H") -> DataCubeService:
    """Create a DataCubeService instance for the given session."""
    return DataCubeService(db=db, dggs_name=dggs_name)
