"""
Enhanced Zonal Statistics Service for TerraCube IDEAS

Provides comprehensive statistical analysis operations for DGGS datasets,
supporting multiple variables and various aggregation methods.
"""

import asyncio
from typing import Dict, List, Optional, Any
from sqlalchemy import select, text, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import CellObject
import logging

logger = logging.getLogger(__name__)


class StatisticMethod:
    """Available statistical aggregation methods."""
    SUM = "sum"
    MEAN = "mean"
    MEDIAN = "median"
    MIN = "min"
    MAX = "max"
    STDDEV = "stddev"
    VARIANCE = "variance"
    COUNT = "count"
    MODE = "mode"
    PERCENTILE = "percentile"
    HISTOGRAM = "histogram"


class ZonalStatsService:
    """
    Enhanced zonal statistics service for multi-variable DGGS analysis.

    Supports comprehensive statistics including:
    - Central tendency (mean, median, mode)
    - Dispersion (stddev, variance, min, max, range)
    - Distribution (percentiles, histogram)
    - Count (cell count)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_zonal_stats(
        self,
        dataset_id: str,
        mask_dataset_id: Optional[str] = None,
        variables: Optional[List[str]] = None,
        operations: Optional[List[str]] = None,
        percentile_bins: Optional[List[int]] = None,
        histogram_bins: int = 10,
        weight_by_area: bool = False
    ) -> Dict[str, Any]:
        """
        Execute comprehensive zonal statistics.

        Args:
            dataset_id: Source dataset to analyze
            mask_dataset_id: Optional mask to constrain analysis (intersection)
            variables: List of attribute keys to analyze
            operations: List of statistics to compute (default: all)
            percentile_bins: Percentile values to compute (default: [25, 50, 75, 90])
            histogram_bins: Number of histogram bins (default: 10)
            weight_by_area: Whether to weight statistics by cell area (default: False)

        Returns:
            Dictionary with results for each variable and operation
        """
        import uuid

        # Validate inputs
        try:
            ds_uuid = uuid.UUID(dataset_id)
            mask_uuid = uuid.UUID(mask_dataset_id) if mask_dataset_id else None
        except ValueError:
            raise ValueError("Invalid dataset_id or mask_dataset_id format")

        if not variables:
            variables = []

        if operations is None:
            operations = [
                StatisticMethod.SUM, StatisticMethod.MEAN, StatisticMethod.MEDIAN,
                StatisticMethod.MIN, StatisticMethod.MAX, StatisticMethod.STDDEV,
                StatisticMethod.VARIANCE, StatisticMethod.COUNT
            ]

        valid_ops = {
            StatisticMethod.SUM, StatisticMethod.MEAN, StatisticMethod.MEDIAN,
            StatisticMethod.MIN, StatisticMethod.MAX, StatisticMethod.STDDEV,
            StatisticMethod.VARIANCE, StatisticMethod.COUNT,
            StatisticMethod.MODE, StatisticMethod.PERCENTILE, StatisticMethod.HISTOGRAM
        }
        for op in operations:
            if op not in valid_ops:
                raise ValueError(f"Unsupported operation: {op}")

        results = {}

        for var in variables:
            var_results = await self._compute_statistics_for_variable(
                ds_uuid, mask_uuid, var, operations,
                percentile_bins, histogram_bins
            )
            results[var] = var_results

        return {
            "dataset_id": dataset_id,
            "mask_dataset_id": str(mask_uuid) if mask_uuid else None,
            "variables": variables,
            "results": results
        }

    async def _compute_statistics_for_variable(
        self,
        dataset_id,
        mask_uuid,
        variable: str,
        operations: List[str],
        percentile_bins: Optional[List[int]],
        histogram_bins: int
    ) -> Dict[str, Any]:
        """
        Compute all requested statistics for a single variable.
        """
        # Base query with mask join
        base_query = (
            select(
                CellObject.dggid,
                CellObject.tid,
                CellObject.value_num
            )
            .where(CellObject.dataset_id == dataset_id)
            .where(CellObject.attr_key == variable)
        )

        # Apply mask if provided
        if mask_uuid:
            mask_query = select(CellObject.dggid).where(
                CellObject.dataset_id == mask_uuid)
            base_query = base_query.where(
                CellObject.dggid.in_(mask_query)
            )

        results = {}

        # Sum
        if StatisticMethod.SUM in operations:
            stmt = select(func.sum(CellObject.value_num).label("sum")).where(
                CellObject.dataset_id == dataset_id,
                CellObject.attr_key == variable
            )
            result = await self.db.execute(stmt)
            row = result.first()
            results["sum"] = float(row[0]) if row and row[0] is not None else 0.0

        # Mean
        if StatisticMethod.MEAN in operations:
            stmt = select(func.avg(CellObject.value_num).label("mean")).where(
                CellObject.dataset_id == dataset_id,
                CellObject.attr_key == variable
            )
            result = await self.db.execute(stmt)
            row = result.first()
            results["mean"] = float(row[0]) if row and row[0] is not None else 0.0

        # Median
        if StatisticMethod.MEDIAN in operations:
            median_stmt = text("""
                SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value_num)
                FROM cell_objects
                WHERE dataset_id = :dataset_id AND attr_key = :variable AND value_num IS NOT NULL
            """)
            result = await self.db.execute(median_stmt, {
                "dataset_id": str(dataset_id), "variable": variable
            })
            row = result.first()
            results["median"] = float(row[0]) if row and row[0] is not None else 0.0

        # Min
        if StatisticMethod.MIN in operations:
            stmt = select(func.min(CellObject.value_num).label("min")).where(
                CellObject.dataset_id == dataset_id,
                CellObject.attr_key == variable
            )
            result = await self.db.execute(stmt)
            row = result.first()
            results["min"] = float(row[0]) if row and row[0] is not None else 0.0

        # Max
        if StatisticMethod.MAX in operations:
            stmt = select(func.max(CellObject.value_num).label("max")).where(
                CellObject.dataset_id == dataset_id,
                CellObject.attr_key == variable
            )
            result = await self.db.execute(stmt)
            row = result.first()
            results["max"] = float(row[0]) if row and row[0] is not None else 0.0

        # StdDev
        if StatisticMethod.STDDEV in operations:
            stmt = select(func.stddev(CellObject.value_num).label("stddev")).where(
                CellObject.dataset_id == dataset_id,
                CellObject.attr_key == variable
            )
            result = await self.db.execute(stmt)
            row = result.first()
            results["stddev"] = float(row[0]) if row and row[0] is not None else 0.0

        # Variance
        if StatisticMethod.VARIANCE in operations:
            stmt = select(func.variance(CellObject.value_num).label("variance")).where(
                CellObject.dataset_id == dataset_id,
                CellObject.attr_key == variable
            )
            result = await self.db.execute(stmt)
            row = result.first()
            results["variance"] = float(row[0]) if row and row[0] is not None else 0.0

        # Count
        if StatisticMethod.COUNT in operations:
            stmt = select(func.count().label("count")).where(
                CellObject.dataset_id == dataset_id,
                CellObject.attr_key == variable,
                CellObject.value_num.isnot(None)
            )
            result = await self.db.execute(stmt)
            row = result.first()
            results["count"] = int(row[0]) if row and row[0] is not None else 0

        # Mode (most frequent value - works for both text and numeric)
        if StatisticMethod.MODE in operations:
            mode_stmt = text("""
                SELECT value_num, value_text, COUNT(*) as cnt
                FROM cell_objects
                WHERE dataset_id = :dataset_id
                    AND attr_key = :variable
                GROUP BY value_num, value_text
                ORDER BY cnt DESC
                LIMIT 1
            """)
            result = await self.db.execute(mode_stmt, {
                "dataset_id": str(dataset_id), "variable": variable
            })
            row = result.first()
            if row:
                results["mode"] = float(row[0]) if row[0] is not None else row[1]
            else:
                results["mode"] = None

        # Percentiles
        if StatisticMethod.PERCENTILE in operations:
            for pct in percentile_bins or [25, 50, 75, 90]:
                pct_stmt = text("""
                    SELECT PERCENTILE_CONT(:pct_frac) WITHIN GROUP (ORDER BY value_num)
                    FROM cell_objects
                    WHERE dataset_id = :dataset_id AND attr_key = :variable AND value_num IS NOT NULL
                """)
                result = await self.db.execute(pct_stmt, {
                    "dataset_id": str(dataset_id), "variable": variable,
                    "pct_frac": pct / 100.0
                })
                row = result.first()
                results[f"percentile_{pct}"] = float(row[0]) if row and row[0] is not None else 0.0

        # Histogram
        if StatisticMethod.HISTOGRAM in operations:
            # Get min/max for binning
            minmax_stmt = text("""
                SELECT MIN(value_num), MAX(value_num)
                FROM cell_objects
                WHERE dataset_id = :dataset_id AND attr_key = :variable AND value_num IS NOT NULL
            """)
            minmax_result = await self.db.execute(minmax_stmt, {
                "dataset_id": str(dataset_id), "variable": variable
            })
            minmax_row = minmax_result.first()

            min_val = float(minmax_row[0]) if minmax_row and minmax_row[0] is not None else 0.0
            max_val = float(minmax_row[1]) if minmax_row and minmax_row[1] is not None else 1.0

            if max_val <= min_val:
                min_val, max_val = 0.0, 1.0

            bin_width = (max_val - min_val) / histogram_bins

            bin_query = text("""
                SELECT
                    FLOOR((value_num - :min_val) / :bin_width) AS bin_num,
                    :min_val + (FLOOR((value_num - :min_val) / :bin_width) * :bin_width) AS bin_start,
                    COUNT(*) AS count
                FROM cell_objects
                WHERE dataset_id = :dataset_id
                    AND attr_key = :variable
                    AND value_num IS NOT NULL
                GROUP BY FLOOR((value_num - :min_val) / :bin_width)
                ORDER BY bin_num
            """)

            result = await self.db.execute(bin_query, {
                "dataset_id": str(dataset_id),
                "variable": variable,
                "min_val": min_val,
                "bin_width": bin_width
            })

            histogram = []
            for row in result:
                bin_start = float(row[1])
                histogram.append({
                    "bin_start": bin_start,
                    "bin_end": bin_start + bin_width,
                    "count": int(row[2])
                })

            results["histogram"] = {
                "bin_width": bin_width,
                "bins": histogram
            }

        return results

    async def compute_correlation_matrix(
        self,
        dataset_id: str,
        variables: List[str],
        mask_dataset_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compute correlation matrix between multiple variables.

        Returns Pearson correlation coefficients for all variable pairs.
        """
        if len(variables) < 2:
            raise ValueError("Need at least 2 variables for correlation")

        results = {
            "variables": variables,
            "correlations": []
        }

        # Build correlation queries for each pair using PostgreSQL CORR()
        for i, var_a in enumerate(variables):
            for var_b in variables[i+1:]:
                stmt = text("""
                    SELECT
                        CORR(a.value_num, b.value_num) AS correlation,
                        COUNT(*) AS cell_count
                    FROM cell_objects a
                    INNER JOIN cell_objects b
                        ON a.dggid = b.dggid AND a.tid = b.tid
                        AND b.dataset_id = :dataset_id AND b.attr_key = :var_b
                    WHERE a.dataset_id = :dataset_id
                        AND a.attr_key = :var_a
                        AND a.value_num IS NOT NULL
                        AND b.value_num IS NOT NULL
                """)

                result = await self.db.execute(stmt, {
                    "dataset_id": dataset_id,
                    "var_a": var_a,
                    "var_b": var_b
                })

                row = result.first()
                results["correlations"].append({
                    "var_a": var_a,
                    "var_b": var_b,
                    "correlation": float(row[0]) if row and row[0] is not None else 0.0,
                    "cell_count": int(row[1]) if row and row[1] is not None else 0
                })

        return results

    async def compute_hotspots(
        self,
        dataset_id: str,
        variable: str,
        mask_dataset_id: Optional[str] = None,
        radius: int = 3,
        method: str = "getis_ord"
    ) -> Dict[str, Any]:
        """
        Compute spatial hotspots using Getis-Ord Gi* statistic.

        For each cell, computes the Gi* z-score by comparing the local
        neighborhood sum to the expected value under spatial randomness.
        """
        radius = max(1, min(radius, 10))

        stmt = text("""
            WITH global_stats AS (
                SELECT
                    AVG(value_num) AS x_bar,
                    STDDEV_POP(value_num) AS s,
                    COUNT(*) AS n
                FROM cell_objects
                WHERE dataset_id = :dataset_id
                    AND attr_key = :variable
                    AND value_num IS NOT NULL
            ),
            kring AS (
                SELECT DISTINCT c.dggid AS center, t.neighbor_dggid AS neighbor
                FROM cell_objects c
                JOIN dgg_topology t ON c.dggid = t.dggid
                WHERE c.dataset_id = :dataset_id
                    AND c.attr_key = :variable
                    AND c.value_num IS NOT NULL
            ),
            local_stats AS (
                SELECT
                    k.center AS dggid,
                    SUM(nb.value_num) AS local_sum,
                    COUNT(nb.value_num) AS wi_count
                FROM kring k
                JOIN cell_objects nb ON k.neighbor = nb.dggid
                    AND nb.dataset_id = :dataset_id
                    AND nb.attr_key = :variable
                    AND nb.value_num IS NOT NULL
                GROUP BY k.center
            )
            SELECT
                ls.dggid,
                c.value_num,
                ls.local_sum,
                ls.wi_count,
                gs.x_bar,
                gs.s,
                gs.n,
                CASE WHEN gs.s > 0 AND gs.n > 1 THEN
                    (ls.local_sum - gs.x_bar * ls.wi_count) /
                    (gs.s * SQRT((gs.n * ls.wi_count - ls.wi_count * ls.wi_count) / NULLIF(gs.n - 1, 0)))
                ELSE 0 END AS gi_z_score
            FROM local_stats ls
            JOIN cell_objects c ON ls.dggid = c.dggid
                AND c.dataset_id = :dataset_id
                AND c.attr_key = :variable
            CROSS JOIN global_stats gs
            ORDER BY gi_z_score DESC
            LIMIT 5000
        """)

        result = await self.db.execute(stmt, {
            "dataset_id": dataset_id,
            "variable": variable
        })

        hotspots = []
        for row in result:
            z = float(row[7]) if row[7] is not None else 0.0
            if abs(z) >= 2.58:
                significance = "p < 0.01"
            elif abs(z) >= 1.96:
                significance = "p < 0.05"
            elif abs(z) >= 1.65:
                significance = "p < 0.10"
            else:
                significance = "not significant"

            hotspots.append({
                "dggid": row[0],
                "value": float(row[1]) if row[1] is not None else None,
                "local_sum": float(row[2]) if row[2] is not None else None,
                "neighbor_count": int(row[3]) if row[3] is not None else 0,
                "gi_z_score": z,
                "type": "hotspot" if z > 0 else "coldspot",
                "significance": significance
            })

        return {
            "dataset_id": dataset_id,
            "variable": variable,
            "method": method,
            "radius": radius,
            "total_cells": len(hotspots),
            "significant_hotspots": len([h for h in hotspots if "not" not in h["significance"] and h["type"] == "hotspot"]),
            "significant_coldspots": len([h for h in hotspots if "not" not in h["significance"] and h["type"] == "coldspot"]),
            "hotspots": hotspots
        }


def get_zonal_stats_service(db: AsyncSession) -> ZonalStatsService:
    """Get a ZonalStatsService instance."""
    return ZonalStatsService(db)
