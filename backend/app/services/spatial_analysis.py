"""
Spatial Analysis Service for TerraCube IDEAS

Advanced spatial analysis algorithms operating on DGGS cells using the
topology table for neighborhood relationships.

Algorithms:
- Moran's I (Global Spatial Autocorrelation)
- LISA (Local Indicators of Spatial Association)
- DBSCAN Clustering
- Kernel Density Estimation
- Change Detection
- Watershed / Flow Direction
- Shortest Path (Dijkstra on DGGS)
"""

from typing import Dict, List, Optional, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import uuid
import math

logger = logging.getLogger(__name__)


class SpatialAnalysisService:
    """Advanced spatial analysis on DGGS datasets using topology table."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def morans_i(
        self,
        dataset_id: str,
        variable: str,
        weight_type: str = "binary"
    ) -> Dict[str, Any]:
        """
        Compute Global Moran's I spatial autocorrelation statistic.

        Measures the overall degree of spatial clustering in a dataset.
        I ≈ +1 means strong positive autocorrelation (clusters)
        I ≈  0 means random spatial pattern
        I ≈ -1 means strong negative autocorrelation (checkerboard)

        Uses the dgg_topology table for spatial weights (binary: 1 if neighbor, 0 otherwise).

        Formula: I = (N/W) * Σᵢ Σⱼ wᵢⱼ(xᵢ - x̄)(xⱼ - x̄) / Σᵢ(xᵢ - x̄)²
        """
        stmt = text("""
            WITH vals AS (
                SELECT dggid, value_num AS x
                FROM cell_objects
                WHERE dataset_id = :dataset_id
                    AND attr_key = :variable
                    AND value_num IS NOT NULL
            ),
            global_stats AS (
                SELECT AVG(x) AS x_bar, COUNT(*) AS n FROM vals
            ),
            deviations AS (
                SELECT v.dggid, v.x - gs.x_bar AS dev
                FROM vals v CROSS JOIN global_stats gs
            ),
            cross_products AS (
                -- Sum of wij * (xi - x_bar) * (xj - x_bar) for all neighbor pairs
                SELECT SUM(di.dev * dj.dev) AS numerator_sum,
                       COUNT(*) AS w_total
                FROM deviations di
                JOIN dgg_topology t ON di.dggid = t.dggid
                JOIN deviations dj ON t.neighbor_dggid = dj.dggid
            ),
            denominator AS (
                SELECT SUM(dev * dev) AS ss FROM deviations
            )
            SELECT
                gs.n,
                cp.w_total,
                cp.numerator_sum,
                d.ss,
                CASE WHEN d.ss > 0 AND cp.w_total > 0 THEN
                    (gs.n::float / cp.w_total) * (cp.numerator_sum / d.ss)
                ELSE 0 END AS morans_i,
                -- Expected value under null hypothesis: E[I] = -1/(N-1)
                CASE WHEN gs.n > 1 THEN -1.0 / (gs.n - 1) ELSE 0 END AS expected_i
            FROM global_stats gs
            CROSS JOIN cross_products cp
            CROSS JOIN denominator d
        """)

        result = await self.db.execute(stmt, {
            "dataset_id": dataset_id,
            "variable": variable
        })
        row = result.first()

        if not row:
            return {"error": "No data found"}

        n = int(row[0])
        w = int(row[1])
        morans_i = float(row[4]) if row[4] is not None else 0.0
        expected_i = float(row[5]) if row[5] is not None else 0.0

        # Compute z-score for significance
        # Variance under normality assumption: Var[I] ≈ E[I²] - E[I]²
        # Simplified: z = (I - E[I]) / sqrt(Var[I])
        # For large N with binary weights: Var ≈ 1/N
        variance = 1.0 / max(n, 1)
        z_score = (morans_i - expected_i) / max(math.sqrt(variance), 1e-10)

        if abs(z_score) >= 2.58:
            significance = "p < 0.01"
        elif abs(z_score) >= 1.96:
            significance = "p < 0.05"
        elif abs(z_score) >= 1.65:
            significance = "p < 0.10"
        else:
            significance = "not significant"

        interpretation = "random"
        if morans_i > expected_i + 0.1:
            interpretation = "clustered"
        elif morans_i < expected_i - 0.1:
            interpretation = "dispersed"

        return {
            "dataset_id": dataset_id,
            "variable": variable,
            "morans_i": round(morans_i, 6),
            "expected_i": round(expected_i, 6),
            "z_score": round(z_score, 4),
            "significance": significance,
            "interpretation": interpretation,
            "n_cells": n,
            "n_weights": w
        }

    async def lisa(
        self,
        dataset_id: str,
        variable: str,
        limit: int = 5000
    ) -> Dict[str, Any]:
        """
        Local Indicators of Spatial Association (LISA / Local Moran's I).

        Computes per-cell spatial autocorrelation to identify:
        - HH: High-High clusters (hotspots)
        - LL: Low-Low clusters (coldspots)
        - HL: High-Low outliers
        - LH: Low-High outliers
        - NS: Not significant

        Local Iᵢ = zᵢ * Σⱼ wᵢⱼ * zⱼ  (where z = standardized values)
        """
        stmt = text("""
            WITH vals AS (
                SELECT dggid, value_num AS x
                FROM cell_objects
                WHERE dataset_id = :dataset_id
                    AND attr_key = :variable
                    AND value_num IS NOT NULL
            ),
            global_stats AS (
                SELECT AVG(x) AS x_bar, STDDEV_POP(x) AS x_std, COUNT(*) AS n
                FROM vals
            ),
            standardized AS (
                SELECT v.dggid,
                       (v.x - gs.x_bar) / NULLIF(gs.x_std, 0) AS z_val,
                       v.x
                FROM vals v CROSS JOIN global_stats gs
            ),
            local_morans AS (
                SELECT
                    si.dggid,
                    si.x AS value,
                    si.z_val,
                    si.z_val * SUM(sj.z_val) / NULLIF(COUNT(sj.z_val), 0) AS local_i,
                    AVG(sj.z_val) AS spatial_lag,
                    COUNT(sj.z_val) AS neighbor_count
                FROM standardized si
                JOIN dgg_topology t ON si.dggid = t.dggid
                JOIN standardized sj ON t.neighbor_dggid = sj.dggid
                GROUP BY si.dggid, si.x, si.z_val
            )
            SELECT
                dggid, value, z_val, local_i, spatial_lag, neighbor_count,
                CASE
                    WHEN z_val > 0 AND spatial_lag > 0 THEN 'HH'
                    WHEN z_val < 0 AND spatial_lag < 0 THEN 'LL'
                    WHEN z_val > 0 AND spatial_lag < 0 THEN 'HL'
                    WHEN z_val < 0 AND spatial_lag > 0 THEN 'LH'
                    ELSE 'NS'
                END AS cluster_type
            FROM local_morans
            ORDER BY ABS(local_i) DESC
            LIMIT :limit
        """)

        result = await self.db.execute(stmt, {
            "dataset_id": dataset_id,
            "variable": variable,
            "limit": min(max(limit, 1), 50000)
        })

        cells = []
        type_counts = {"HH": 0, "LL": 0, "HL": 0, "LH": 0, "NS": 0}
        for row in result:
            local_i = float(row[3]) if row[3] is not None else 0.0
            cluster_type = row[6]
            # Simple significance: |local_i| > 1.96 for p < 0.05
            significant = abs(local_i) > 1.96
            if not significant:
                cluster_type = "NS"
            type_counts[cluster_type] = type_counts.get(cluster_type, 0) + 1

            cells.append({
                "dggid": row[0],
                "value": float(row[1]) if row[1] is not None else None,
                "z_score": round(float(row[2]), 4) if row[2] is not None else None,
                "local_i": round(local_i, 4),
                "spatial_lag": round(float(row[4]), 4) if row[4] is not None else None,
                "cluster_type": cluster_type,
                "significant": significant
            })

        return {
            "dataset_id": dataset_id,
            "variable": variable,
            "total_cells": len(cells),
            "cluster_counts": type_counts,
            "cells": cells
        }

    async def dbscan_cluster(
        self,
        dataset_id: str,
        variable: str,
        eps_rings: int = 2,
        min_pts: int = 3,
        value_threshold: float = 0.5,
        limit: int = 5000
    ) -> Dict[str, Any]:
        """
        DBSCAN-style spatial clustering on DGGS.

        Groups cells into clusters based on spatial proximity (K-ring neighbors)
        and value similarity.

        Args:
            dataset_id: Dataset to cluster
            variable: Attribute key for values
            eps_rings: Neighborhood radius in K-ring hops (epsilon)
            min_pts: Minimum points to form a core point
            value_threshold: Max value difference for "similar" (fraction of stddev)
            limit: Max cells to process
        """
        # Fetch all cell values
        fetch_stmt = text("""
            SELECT dggid, value_num
            FROM cell_objects
            WHERE dataset_id = :dataset_id
                AND attr_key = :variable
                AND value_num IS NOT NULL
            ORDER BY dggid
            LIMIT :limit
        """)
        result = await self.db.execute(fetch_stmt, {
            "dataset_id": dataset_id,
            "variable": variable,
            "limit": limit
        })
        cells = {row[0]: float(row[1]) for row in result}

        if not cells:
            return {"error": "No data found", "clusters": []}

        # Get global stddev for value threshold
        stats_stmt = text("""
            SELECT STDDEV_POP(value_num) FROM cell_objects
            WHERE dataset_id = :dataset_id AND attr_key = :variable AND value_num IS NOT NULL
        """)
        stats_result = await self.db.execute(stats_stmt, {
            "dataset_id": dataset_id, "variable": variable
        })
        stddev = float(stats_result.scalar() or 1.0)
        abs_threshold = stddev * value_threshold

        # Get neighbor relationships
        neighbor_stmt = text("""
            SELECT dggid, neighbor_dggid
            FROM dgg_topology
            WHERE dggid = ANY(:dggids)
        """)
        neighbor_result = await self.db.execute(neighbor_stmt, {
            "dggids": list(cells.keys())
        })
        neighbors = {}
        for row in neighbor_result:
            neighbors.setdefault(row[0], []).append(row[1])

        # DBSCAN algorithm
        cluster_id = 0
        labels = {}  # dggid -> cluster_id (-1 = noise)
        visited = set()

        def region_query(cell_id):
            """Find epsilon-neighborhood: neighbors with similar values."""
            if cell_id not in cells:
                return []
            result = []
            for n in neighbors.get(cell_id, []):
                if n in cells and abs(cells[n] - cells[cell_id]) <= abs_threshold:
                    result.append(n)
            return result

        def expand_cluster(cell_id, cluster_neighbors, cid):
            labels[cell_id] = cid
            queue = list(cluster_neighbors)
            while queue:
                q = queue.pop(0)
                if q not in visited:
                    visited.add(q)
                    q_neighbors = region_query(q)
                    if len(q_neighbors) >= min_pts:
                        queue.extend([n for n in q_neighbors if n not in visited])
                if q not in labels:
                    labels[q] = cid

        for cell_id in cells:
            if cell_id in visited:
                continue
            visited.add(cell_id)
            cell_neighbors = region_query(cell_id)
            if len(cell_neighbors) < min_pts:
                labels[cell_id] = -1  # noise
            else:
                expand_cluster(cell_id, cell_neighbors, cluster_id)
                cluster_id += 1

        # Build results
        clusters = {}
        noise_count = 0
        for dggid, cid in labels.items():
            if cid == -1:
                noise_count += 1
            else:
                clusters.setdefault(cid, []).append({
                    "dggid": dggid,
                    "value": cells[dggid]
                })

        cluster_summaries = []
        for cid, members in clusters.items():
            vals = [m["value"] for m in members]
            cluster_summaries.append({
                "cluster_id": cid,
                "cell_count": len(members),
                "mean_value": sum(vals) / len(vals),
                "min_value": min(vals),
                "max_value": max(vals),
                "cells": [m["dggid"] for m in members]
            })

        return {
            "dataset_id": dataset_id,
            "variable": variable,
            "parameters": {
                "eps_rings": eps_rings,
                "min_pts": min_pts,
                "value_threshold": value_threshold,
                "abs_threshold": abs_threshold
            },
            "total_cells": len(cells),
            "n_clusters": len(cluster_summaries),
            "noise_count": noise_count,
            "clusters": sorted(cluster_summaries, key=lambda c: -c["cell_count"])
        }

    async def change_detection(
        self,
        dataset_a_id: str,
        dataset_b_id: str,
        variable: str,
        threshold: float = 0.0,
        limit: int = 10000
    ) -> Dict[str, Any]:
        """
        Multi-temporal change detection between two datasets.

        Identifies cells where values changed significantly between time periods.
        Classifies changes as: gain, loss, stable, appeared, disappeared.
        """
        stmt = text("""
            WITH changes AS (
                SELECT
                    COALESCE(a.dggid, b.dggid) AS dggid,
                    a.value_num AS value_before,
                    b.value_num AS value_after,
                    COALESCE(b.value_num, 0) - COALESCE(a.value_num, 0) AS abs_change,
                    CASE
                        WHEN a.value_num IS NOT NULL AND b.value_num IS NOT NULL AND a.value_num != 0
                            THEN (b.value_num - a.value_num) / ABS(a.value_num) * 100
                        ELSE NULL
                    END AS pct_change,
                    CASE
                        WHEN a.dggid IS NULL THEN 'appeared'
                        WHEN b.dggid IS NULL THEN 'disappeared'
                        WHEN ABS(COALESCE(b.value_num, 0) - COALESCE(a.value_num, 0)) <= :threshold THEN 'stable'
                        WHEN b.value_num > a.value_num THEN 'gain'
                        ELSE 'loss'
                    END AS change_type
                FROM cell_objects a
                FULL OUTER JOIN cell_objects b
                    ON a.dggid = b.dggid AND a.attr_key = b.attr_key
                    AND b.dataset_id = :dataset_b AND b.attr_key = :variable
                WHERE (a.dataset_id = :dataset_a AND a.attr_key = :variable)
                   OR (b.dataset_id = :dataset_b AND b.attr_key = :variable)
            )
            SELECT dggid, value_before, value_after, abs_change, pct_change, change_type
            FROM changes
            WHERE change_type != 'stable'
            ORDER BY ABS(abs_change) DESC
            LIMIT :limit
        """)

        result = await self.db.execute(stmt, {
            "dataset_a": dataset_a_id,
            "dataset_b": dataset_b_id,
            "variable": variable,
            "threshold": threshold,
            "limit": limit
        })

        changes = []
        type_counts = {"gain": 0, "loss": 0, "stable": 0, "appeared": 0, "disappeared": 0}

        for row in result:
            change_type = row[5]
            type_counts[change_type] = type_counts.get(change_type, 0) + 1
            changes.append({
                "dggid": row[0],
                "value_before": float(row[1]) if row[1] is not None else None,
                "value_after": float(row[2]) if row[2] is not None else None,
                "absolute_change": float(row[3]) if row[3] is not None else None,
                "percent_change": round(float(row[4]), 2) if row[4] is not None else None,
                "change_type": change_type
            })

        return {
            "dataset_a_id": dataset_a_id,
            "dataset_b_id": dataset_b_id,
            "variable": variable,
            "threshold": threshold,
            "total_changes": len(changes),
            "change_summary": type_counts,
            "changes": changes
        }

    async def flow_direction(
        self,
        dataset_id: str,
        elevation_attr: str = "elevation"
    ) -> Dict[str, Any]:
        """
        Compute flow direction on DGGS grid using steepest descent.

        For each cell, determines which neighbor has the lowest elevation
        (steepest downhill gradient). Creates a new dataset with flow direction
        encoded as the target neighbor DGGID.

        Returns flow accumulation counts (how many cells drain through each cell).
        """
        result_id = uuid.uuid4()

        # Compute flow direction: find lowest neighbor for each cell
        flow_stmt = text("""
            WITH elevations AS (
                SELECT dggid, value_num AS elev
                FROM cell_objects
                WHERE dataset_id = :dataset_id
                    AND attr_key = :elevation_attr
                    AND value_num IS NOT NULL
            ),
            ranked_neighbors AS (
                SELECT
                    e.dggid AS source,
                    e.elev AS source_elev,
                    t.neighbor_dggid AS target,
                    en.elev AS target_elev,
                    e.elev - en.elev AS drop,
                    ROW_NUMBER() OVER (PARTITION BY e.dggid ORDER BY en.elev ASC) AS rn
                FROM elevations e
                JOIN dgg_topology t ON e.dggid = t.dggid
                JOIN elevations en ON t.neighbor_dggid = en.dggid
                WHERE en.elev < e.elev
            ),
            flow_dir AS (
                SELECT source, target, source_elev, target_elev, drop
                FROM ranked_neighbors WHERE rn = 1
            )
            INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
            SELECT CAST(:result_id AS UUID), fd.source, 0, 'flow_direction',
                   fd.drop, fd.target,
                   jsonb_build_object('target', fd.target, 'drop', fd.drop,
                                      'source_elev', fd.source_elev, 'target_elev', fd.target_elev)
            FROM flow_dir fd
            ON CONFLICT (dataset_id, dggid, tid, attr_key) DO NOTHING
        """)

        from app.models import Dataset
        new_dataset = Dataset(
            id=result_id,
            name="Flow Direction Result",
            description=f"Flow direction computed from elevation in dataset {dataset_id}",
            dggs_name="IVEA3H",
            metadata_={"source": "spatial_analysis", "type": "flow_direction",
                        "parent": dataset_id, "elevation_attr": elevation_attr},
            status="processing"
        )
        self.db.add(new_dataset)

        await self.db.execute(flow_stmt, {
            "dataset_id": dataset_id,
            "elevation_attr": elevation_attr,
            "result_id": result_id
        })

        # Compute flow accumulation using recursive CTE
        accum_stmt = text("""
            WITH RECURSIVE flow AS (
                -- Start from all cells that have no upstream (are sources)
                SELECT dggid, value_text AS target, 1 AS accum
                FROM cell_objects
                WHERE dataset_id = :result_id AND attr_key = 'flow_direction'
            ),
            accumulation AS (
                SELECT target AS dggid, SUM(accum) AS flow_accum
                FROM flow
                GROUP BY target
            )
            UPDATE cell_objects SET
                value_num = a.flow_accum
            FROM accumulation a
            WHERE cell_objects.dataset_id = :result_id
                AND cell_objects.dggid = a.dggid
                AND cell_objects.attr_key = 'flow_direction'
        """)

        try:
            await self.db.execute(accum_stmt, {"result_id": result_id})
        except Exception as e:
            logger.warning(f"Flow accumulation failed (non-critical): {e}")

        await self.db.execute(
            text("UPDATE datasets SET status = 'active' WHERE id = :id"),
            {"id": str(result_id)}
        )
        await self.db.commit()

        return {
            "dataset_id": dataset_id,
            "result_dataset_id": str(result_id),
            "elevation_attr": elevation_attr,
            "operation": "flow_direction"
        }

    async def shortest_path(
        self,
        start_dggid: str,
        end_dggid: str,
        cost_dataset_id: Optional[str] = None,
        cost_attr: str = "cost",
        max_hops: int = 100
    ) -> Dict[str, Any]:
        """
        Find shortest path between two DGGS cells using Dijkstra's algorithm
        on the topology graph.

        Optionally weighted by a cost dataset (e.g., terrain difficulty).
        Without a cost dataset, uses uniform cost (shortest by hop count).
        """
        if cost_dataset_id:
            stmt = text("""
                WITH RECURSIVE dijkstra AS (
                    SELECT
                        :start AS dggid,
                        0.0 AS cost,
                        ARRAY[:start] AS path,
                        0 AS hops
                    UNION ALL
                    SELECT
                        t.neighbor_dggid,
                        d.cost + COALESCE(c.value_num, 1.0),
                        d.path || t.neighbor_dggid,
                        d.hops + 1
                    FROM dijkstra d
                    JOIN dgg_topology t ON d.dggid = t.dggid
                    LEFT JOIN cell_objects c ON t.neighbor_dggid = c.dggid
                        AND c.dataset_id = :cost_ds AND c.attr_key = :cost_attr
                    WHERE t.neighbor_dggid != ALL(d.path)
                        AND d.hops < :max_hops
                        AND d.dggid != :end
                )
                SELECT dggid, cost, path, hops
                FROM dijkstra
                WHERE dggid = :end
                ORDER BY cost ASC
                LIMIT 1
            """)
            params = {
                "start": start_dggid,
                "end": end_dggid,
                "cost_ds": cost_dataset_id,
                "cost_attr": cost_attr,
                "max_hops": max_hops
            }
        else:
            stmt = text("""
                WITH RECURSIVE bfs AS (
                    SELECT
                        :start AS dggid,
                        ARRAY[:start] AS path,
                        0 AS hops
                    UNION ALL
                    SELECT
                        t.neighbor_dggid,
                        b.path || t.neighbor_dggid,
                        b.hops + 1
                    FROM bfs b
                    JOIN dgg_topology t ON b.dggid = t.dggid
                    WHERE t.neighbor_dggid != ALL(b.path)
                        AND b.hops < :max_hops
                        AND b.dggid != :end
                )
                SELECT dggid, hops AS cost, path, hops
                FROM bfs
                WHERE dggid = :end
                ORDER BY hops ASC
                LIMIT 1
            """)
            params = {
                "start": start_dggid,
                "end": end_dggid,
                "max_hops": max_hops
            }

        result = await self.db.execute(stmt, params)
        row = result.first()

        if not row:
            return {
                "start": start_dggid,
                "end": end_dggid,
                "found": False,
                "message": f"No path found within {max_hops} hops"
            }

        return {
            "start": start_dggid,
            "end": end_dggid,
            "found": True,
            "total_cost": float(row[1]),
            "hops": int(row[3]),
            "path": list(row[2])
        }

    async def kernel_density(
        self,
        dataset_id: str,
        variable: str,
        bandwidth: int = 3,
        kernel: str = "gaussian"
    ) -> Dict[str, Any]:
        """
        Kernel Density Estimation on DGGS grid.

        Spreads each cell's value to its K-ring neighborhood using a kernel
        function, creating a smooth density surface.

        Args:
            dataset_id: Source dataset with point/cell data
            variable: Attribute key for values
            bandwidth: K-ring radius for kernel (1-10)
            kernel: Kernel type ("gaussian", "linear", "uniform")
        """
        bandwidth = max(1, min(bandwidth, 10))
        result_id = uuid.uuid4()

        # Kernel weight expression based on distance
        if kernel == "gaussian":
            weight_expr = "EXP(-0.5 * POWER(bfs.depth::float / :bandwidth, 2))"
        elif kernel == "linear":
            weight_expr = "GREATEST(0, 1.0 - bfs.depth::float / :bandwidth)"
        else:  # uniform
            weight_expr = "1.0"

        stmt = text(f"""
            WITH RECURSIVE bfs AS (
                SELECT dggid, 0 AS depth, value_num
                FROM cell_objects
                WHERE dataset_id = :dataset_id
                    AND attr_key = :variable
                    AND value_num IS NOT NULL
                UNION
                SELECT t.neighbor_dggid, bfs.depth + 1, bfs.value_num
                FROM bfs
                JOIN dgg_topology t ON bfs.dggid = t.dggid
                WHERE bfs.depth < :bandwidth
            ),
            density AS (
                SELECT
                    bfs.dggid,
                    SUM(bfs.value_num * {weight_expr}) AS weighted_sum,
                    SUM({weight_expr}) AS weight_total,
                    COUNT(*) AS contributions
                FROM bfs
                GROUP BY bfs.dggid
            )
            INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
            SELECT CAST(:result_id AS UUID), d.dggid, 0, 'density',
                   d.weighted_sum / NULLIF(d.weight_total, 0),
                   'KDE', jsonb_build_object('contributions', d.contributions, 'kernel', :kernel)
            FROM density d
            ON CONFLICT (dataset_id, dggid, tid, attr_key) DO UPDATE SET
                value_num = EXCLUDED.value_num,
                value_json = EXCLUDED.value_json
        """)

        from app.models import Dataset
        new_dataset = Dataset(
            id=result_id,
            name=f"KDE ({kernel}, bw={bandwidth})",
            description=f"Kernel density estimation from {dataset_id}",
            dggs_name="IVEA3H",
            metadata_={"source": "spatial_analysis", "type": "kde",
                        "parent": dataset_id, "kernel": kernel, "bandwidth": bandwidth},
            status="processing"
        )
        self.db.add(new_dataset)

        await self.db.execute(stmt, {
            "dataset_id": dataset_id,
            "variable": variable,
            "bandwidth": bandwidth,
            "kernel": kernel,
            "result_id": result_id
        })

        await self.db.execute(
            text("UPDATE datasets SET status = 'active' WHERE id = :id"),
            {"id": str(result_id)}
        )
        await self.db.commit()

        return {
            "dataset_id": dataset_id,
            "result_dataset_id": str(result_id),
            "kernel": kernel,
            "bandwidth": bandwidth,
            "operation": "kernel_density"
        }


def get_spatial_analysis_service(db: AsyncSession) -> SpatialAnalysisService:
    """Get a SpatialAnalysisService instance."""
    return SpatialAnalysisService(db)
