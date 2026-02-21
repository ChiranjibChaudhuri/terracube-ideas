from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.models import CellObject, Dataset
import uuid
from typing import Optional, Any, List, Dict
import logging

logger = logging.getLogger(__name__)

class OpsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _parse_uuid(self, value: str, label: str):
        try:
            return uuid.UUID(value)
        except ValueError:
            raise ValueError(f"Invalid {label}")

    def _coerce_number(self, value: Any):
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    async def execute_query(self, dataset_id_str: str, query_type: str, key: str, 
                          min_val: Optional[float] = None, max_val: Optional[float] = None, 
                          op: Optional[str] = None, value: Optional[Any] = None, 
                          agg: Optional[str] = None, group_by: Optional[str] = None, 
                          limit: int = 5000) -> Dict[str, Any]:
        
        dataset_id = self._parse_uuid(dataset_id_str, "datasetId")
        limit = min(max(limit or 1, 1), 5000)

        if query_type == "range":
            if min_val is None and max_val is None:
                raise ValueError("Provide min or max for range query.")

            stmt = select(
                CellObject.dggid,
                CellObject.tid,
                CellObject.attr_key,
                CellObject.value_text,
                CellObject.value_num,
                CellObject.value_json,
            ).where(
                CellObject.dataset_id == dataset_id,
                CellObject.attr_key == key,
            )

            if min_val is not None:
                stmt = stmt.where(CellObject.value_num >= min_val)
            if max_val is not None:
                stmt = stmt.where(CellObject.value_num <= max_val)

            stmt = stmt.limit(limit)
            result = await self.db.execute(stmt)
            return {"rows": [dict(row) for row in result.mappings().all()]}

        if query_type == "filter":
            if op not in ("eq", None):
                raise ValueError("Only 'eq' filter is supported.")
            if value is None:
                raise ValueError("Provide a value for filter.")

            numeric_value = self._coerce_number(value)
            stmt = select(
                CellObject.dggid,
                CellObject.tid,
                CellObject.attr_key,
                CellObject.value_text,
                CellObject.value_num,
                CellObject.value_json,
            ).where(
                CellObject.dataset_id == dataset_id,
                CellObject.attr_key == key,
            )

            if numeric_value is not None:
                stmt = stmt.where(CellObject.value_num == numeric_value)
            else:
                stmt = stmt.where(CellObject.value_text == str(value))

            stmt = stmt.limit(limit)
            result = await self.db.execute(stmt)
            return {"rows": [dict(row) for row in result.mappings().all()]}

        if query_type == "aggregate":
            if group_by and group_by != "dggid":
                raise ValueError("Only groupBy=dggid is supported.")
            agg = (agg or "avg").lower()
            agg_map = {
                "avg": func.avg,
                "mean": func.avg,
                "sum": func.sum,
                "min": func.min,
                "max": func.max,
                "count": func.count,
            }
            agg_fn = agg_map.get(agg)
            if not agg_fn:
                raise ValueError(f"Unsupported aggregation: {agg}")

            value_col = agg_fn(CellObject.value_num).label("value")
            stmt = (
                select(CellObject.dggid.label("dggid"), value_col)
                .where(CellObject.dataset_id == dataset_id, CellObject.attr_key == key)
                .group_by(CellObject.dggid)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            return {"rows": [dict(row) for row in result.mappings().all()]}

        raise ValueError("Unsupported query type.")

    async def execute_spatial_op(self, op_type: str, dataset_a_id: str, dataset_b_id: Optional[str],
                               limit: int = 1000) -> Dict[str, Any]:
        """
        Execute a spatial operation between datasets and store result as new dataset.
        All operations are performed in a transaction for atomicity.
        """
        dataset_a = self._parse_uuid(dataset_a_id, "datasetAId")
        dataset_b = self._parse_uuid(dataset_b_id, "datasetBId") if dataset_b_id else None

        limit = min(max(limit or 1, 1), 50000)

        # Validate operation type
        valid_ops = {
            "intersection", "union", "difference", "symmetric_difference",
            "buffer", "buffer_weighted", "aggregate", "propagate",
            "contour", "idw_interpolation"
        }
        if op_type not in valid_ops:
            raise ValueError(f"Invalid operation type: {op_type}. Must be one of {valid_ops}")

        ids_to_fetch = [dataset_a]
        if dataset_b:
            ids_to_fetch.append(dataset_b)

        result = await self.db.execute(select(Dataset).where(Dataset.id.in_(ids_to_fetch)))
        datasets = {str(ds.id): ds for ds in result.scalars().all()}

        if str(dataset_a) not in datasets:
            raise ValueError(f"Dataset A not found: {dataset_a}")
        if dataset_b and str(dataset_b) not in datasets:
            raise ValueError(f"Dataset B not found: {dataset_b}")

        ds_a = datasets[str(dataset_a)]
        ds_b = datasets.get(str(dataset_b)) if dataset_b else None

        if ds_b and ds_a.dggs_name != ds_b.dggs_name:
            raise ValueError("DGGS mismatch between datasets. Both datasets must use same DGGS.")

        # Verify topology table exists for operations that need it
        topology_ops = {"buffer", "buffer_weighted", "aggregate", "propagate", "contour", "idw_interpolation"}
        if op_type in topology_ops:
            topology_check = await self.db.execute(text(
                "SELECT 1 FROM dgg_topology LIMIT 1"
            ))
            if topology_check.scalar() is None:
                raise ValueError(
                    "Topology table is empty. Run topology population first: "
                    "python -m app.scripts.populate_topology"
                )

        # Create new result dataset
        new_id = uuid.uuid4()
        op_name = op_type.capitalize()

        desc = f"{op_name} of {ds_a.name}"
        if ds_b:
            desc += f" and {ds_b.name}"

        parents = [str(dataset_a)]
        if dataset_b:
            parents.append(str(dataset_b))

        async with self.db.begin():
            try:
                new_dataset = Dataset(
                    id=new_id,
                    name=f"{op_name} Result",
                    description=desc,
                    dggs_name=ds_a.dggs_name,
                    level=ds_a.level,
                    metadata_={"source": "spatial_op", "type": op_type, "parents": parents},
                    status="processing"
                )
                self.db.add(new_dataset)

                # Insert result cells based on operation type
                if op_type == "intersection":
                    await self._execute_intersection(new_id, dataset_a, dataset_b)

                elif op_type == "union":
                    await self._execute_union(new_id, dataset_a, dataset_b)

                elif op_type == "difference":
                    await self._execute_difference(new_id, dataset_a, dataset_b)

                elif op_type == "buffer":
                    iterations = max(1, min(limit or 1, 10))
                    await self._execute_buffer(new_id, dataset_a, iterations)

                elif op_type == "aggregate":
                    agg_method = "avg"  # Default; can be overridden via metadata
                    await self._execute_aggregate(new_id, dataset_a, agg_method)

                elif op_type == "symmetric_difference":
                    await self._execute_symmetric_difference(new_id, dataset_a, dataset_b)

                elif op_type == "buffer_weighted":
                    iterations = max(1, min(limit or 3, 10))
                    await self._execute_buffer_weighted(new_id, dataset_a, iterations)

                elif op_type == "contour":
                    await self._execute_contour(new_id, dataset_a, limit)

                elif op_type == "idw_interpolation":
                    radius = max(1, min(limit or 3, 10))
                    await self._execute_idw_interpolation(new_id, dataset_a, radius)

                elif op_type == "propagate":
                    iterations = max(1, min(limit or 5, 20))
                    if dataset_b:
                        await self._execute_propagate_constrained(new_id, dataset_a, dataset_b, iterations)
                    else:
                        await self._execute_buffer(new_id, dataset_a, iterations)

                # Update status to active
                await self.db.execute(
                    text("UPDATE datasets SET status = 'active' WHERE id = :id"),
                    {"id": str(new_id)}
                )

                await self.db.commit()
                logger.info(f"Completed spatial operation {op_type}, created dataset {new_id}")

                return {
                    "status": "success",
                    "newDatasetId": str(new_id),
                    "operation": op_type,
                    "resultName": f"{op_name} Result"
                }

            except Exception as e:
                await self.db.rollback()
                logger.error(f"Spatial operation {op_type} failed: {e}")
                # Clean up the orphaned dataset record
                try:
                    await self.db.execute(
                        text("DELETE FROM datasets WHERE id = :id"),
                        {"id": str(new_id)}
                    )
                    await self.db.commit()
                except Exception:
                    pass
                raise ValueError(f"Spatial operation failed: {str(e)}")

    async def _execute_intersection(self, new_id: str, dataset_a: str, dataset_b: str):
        """Geometric intersection: cells present in both A and B"""
        sql = text("""
            INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
            SELECT :new_id, a.dggid, COALESCE(a.tid, b.tid), 'intersection',
                   CASE WHEN a.value_num IS NOT NULL AND b.value_num IS NOT NULL
                       THEN (a.value_num + b.value_num) / 2
                       ELSE COALESCE(a.value_num, b.value_num) END,
                   COALESCE(a.value_text, b.value_text),
                   jsonb_build_object('a', a.value_json, 'b', b.value_json)
            FROM cell_objects a
            INNER JOIN cell_objects b ON a.dggid = b.dggid AND a.tid = b.tid AND a.attr_key = b.attr_key
            WHERE a.dataset_id = :dataset_a AND b.dataset_id = :dataset_b
            ON CONFLICT (dataset_id, dggid, tid, attr_key) DO UPDATE SET
                value_num = EXCLUDED.value_num,
                value_text = EXCLUDED.value_text,
                value_json = EXCLUDED.value_json
        """)
        await self.db.execute(sql, {"new_id": new_id, "dataset_a": dataset_a, "dataset_b": dataset_b})

    async def _execute_union(self, new_id: str, dataset_a: str, dataset_b: Optional[str]):
        """Geometric union: all cells from A and B"""
        # Insert all cells from A
        await self.db.execute(text("""
            INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
            SELECT :new_id, dggid, tid, attr_key, value_num, value_text, value_json
            FROM cell_objects WHERE dataset_id = :dataset_a
        """), {"new_id": new_id, "dataset_a": dataset_a})

        # Insert cells from B that don't exist in A (by dggid, tid, attr_key)
        if dataset_b:
            await self.db.execute(text("""
                INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
                SELECT :new_id, b.dggid, b.tid, b.attr_key, b.value_num, b.value_text, b.value_json
                FROM cell_objects b
                WHERE b.dataset_id = :dataset_b
                AND NOT EXISTS (
                    SELECT 1 FROM cell_objects a
                    WHERE a.dataset_id = :dataset_a
                    AND a.dggid = b.dggid
                    AND a.tid = b.tid
                    AND a.attr_key = b.attr_key
                )
            """), {"new_id": new_id, "dataset_a": dataset_a, "dataset_b": dataset_b})

    async def _execute_difference(self, new_id: str, dataset_a: str, dataset_b: str):
        """Geometric difference: cells in A that are not in B"""
        await self.db.execute(text("""
            INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
            SELECT :new_id, a.dggid, a.tid, a.attr_key, a.value_num, a.value_text, a.value_json
            FROM cell_objects a
            LEFT JOIN cell_objects b ON a.dggid = b.dggid AND a.tid = b.tid AND a.attr_key = b.attr_key
                AND b.dataset_id = :dataset_b
            WHERE a.dataset_id = :dataset_a AND b.dggid IS NULL
        """), {"new_id": new_id, "dataset_a": dataset_a, "dataset_b": dataset_b})

    async def _execute_buffer(self, new_id: str, dataset_a: str, iterations: int):
        """Buffer: expand by K-ring neighbors using topology table"""
        await self.db.execute(text("""
            WITH RECURSIVE bfs AS (
                SELECT dggid, 0 as depth FROM cell_objects WHERE dataset_id = :dataset_a
                UNION
                SELECT t.neighbor_dggid, bfs.depth + 1
                FROM bfs
                JOIN dgg_topology t ON bfs.dggid = t.dggid
                WHERE bfs.depth < :iterations
            )
            INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
            SELECT DISTINCT CAST(:new_id AS UUID), b.dggid, 0, 'buffer',
                   CAST(NULL AS FLOAT), 'Buffer', CAST(NULL AS JSONB)
            FROM bfs b
        """), {"new_id": new_id, "dataset_a": dataset_a, "iterations": iterations})

    async def _execute_aggregate(self, new_id: str, dataset_a: str, agg_method: str = "avg"):
        """Aggregate: coarsen by moving to parent cells using topology table.
        Supports: avg, sum, min, max, count, stddev."""
        agg_sql_map = {
            "avg": "AVG", "mean": "AVG", "sum": "SUM",
            "min": "MIN", "max": "MAX", "count": "COUNT",
            "stddev": "STDDEV"
        }
        agg_func = agg_sql_map.get(agg_method.lower(), "AVG")

        await self.db.execute(text(f"""
            INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
            SELECT CAST(:new_id AS UUID), t.parent_dggid, 0, 'aggregate',
                   {agg_func}(a.value_num), 'Aggregated',
                   jsonb_build_object('method', :agg_method, 'child_count', COUNT(*))
            FROM cell_objects a
            JOIN dgg_topology t ON a.dggid = t.dggid
            WHERE a.dataset_id = :dataset_a
            AND t.parent_dggid IS NOT NULL
            GROUP BY t.parent_dggid
        """), {"new_id": new_id, "dataset_a": dataset_a, "agg_method": agg_method})

    async def _execute_propagate_constrained(self, new_id: str, dataset_a: str, dataset_b: str, iterations: int):
        """Constrained propagation (flood fill with mask)"""
        await self.db.execute(text("""
            WITH RECURSIVE spread AS (
                SELECT dggid, 0 as depth FROM cell_objects WHERE dataset_id = :dataset_a
                UNION
                SELECT t.neighbor_dggid, s.depth + 1
                FROM spread s
                JOIN dgg_topology t ON s.dggid = t.dggid
                JOIN cell_objects mask ON t.neighbor_dggid = mask.dggid AND mask.dataset_id = :dataset_b
                WHERE s.depth < :iterations
            )
            INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
            SELECT DISTINCT CAST(:new_id AS UUID), s.dggid, 0, 'propagate',
                   CAST(NULL AS FLOAT), 'Spread', CAST(NULL AS JSONB)
            FROM spread s
        """), {"new_id": new_id, "dataset_a": dataset_a, "dataset_b": dataset_b, "iterations": iterations})

    async def _execute_symmetric_difference(self, new_id: str, dataset_a: str, dataset_b: str):
        """Symmetric difference: cells in A XOR B (in one but not both)"""
        await self.db.execute(text("""
            INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
            SELECT :new_id, a.dggid, a.tid, a.attr_key, a.value_num, a.value_text, a.value_json
            FROM cell_objects a
            LEFT JOIN cell_objects b ON a.dggid = b.dggid AND a.tid = b.tid AND a.attr_key = b.attr_key
                AND b.dataset_id = :dataset_b
            WHERE a.dataset_id = :dataset_a AND b.dggid IS NULL
            UNION ALL
            SELECT :new_id, b.dggid, b.tid, b.attr_key, b.value_num, b.value_text, b.value_json
            FROM cell_objects b
            LEFT JOIN cell_objects a ON b.dggid = a.dggid AND b.tid = a.tid AND b.attr_key = a.attr_key
                AND a.dataset_id = :dataset_a
            WHERE b.dataset_id = :dataset_b AND a.dggid IS NULL
            ON CONFLICT (dataset_id, dggid, tid, attr_key) DO NOTHING
        """), {"new_id": new_id, "dataset_a": dataset_a, "dataset_b": dataset_b})

    async def _execute_buffer_weighted(self, new_id: str, dataset_a: str, iterations: int):
        """Distance-weighted buffer: expand by K-ring with distance decay.
        Each cell gets a value_num = 1.0 / (depth + 1), creating a distance field."""
        await self.db.execute(text("""
            WITH RECURSIVE bfs AS (
                SELECT DISTINCT dggid, 0 AS depth
                FROM cell_objects WHERE dataset_id = :dataset_a
                UNION
                SELECT t.neighbor_dggid, bfs.depth + 1
                FROM bfs
                JOIN dgg_topology t ON bfs.dggid = t.dggid
                WHERE bfs.depth < :iterations
            ),
            min_depth AS (
                SELECT dggid, MIN(depth) AS depth FROM bfs GROUP BY dggid
            )
            INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
            SELECT DISTINCT CAST(:new_id AS UUID), md.dggid, 0, 'buffer_distance',
                   1.0 / (md.depth + 1.0),
                   CASE WHEN md.depth = 0 THEN 'Source' ELSE 'Buffer' END,
                   jsonb_build_object('distance', md.depth)
            FROM min_depth md
            ON CONFLICT (dataset_id, dggid, tid, attr_key) DO UPDATE SET
                value_num = EXCLUDED.value_num,
                value_json = EXCLUDED.value_json
        """), {"new_id": new_id, "dataset_a": dataset_a, "iterations": iterations})

    async def _execute_contour(self, new_id: str, dataset_a: str, num_levels: int):
        """Contour/isoline detection: find cells on boundaries where values cross thresholds.
        Generates num_levels contour lines evenly spaced between min and max values."""
        num_levels = max(2, min(num_levels, 50))
        await self.db.execute(text("""
            WITH value_range AS (
                SELECT MIN(value_num) AS min_val, MAX(value_num) AS max_val
                FROM cell_objects
                WHERE dataset_id = :dataset_a AND value_num IS NOT NULL
            ),
            thresholds AS (
                SELECT generate_series(1, :num_levels - 1) AS level_idx,
                       min_val + (max_val - min_val) * generate_series(1, :num_levels - 1)::float / :num_levels AS threshold
                FROM value_range
            ),
            contour_cells AS (
                SELECT DISTINCT a.dggid, a.value_num, th.threshold, th.level_idx
                FROM cell_objects a
                JOIN dgg_topology t ON a.dggid = t.dggid
                JOIN cell_objects b ON t.neighbor_dggid = b.dggid
                    AND b.dataset_id = :dataset_a AND b.value_num IS NOT NULL
                CROSS JOIN thresholds th
                WHERE a.dataset_id = :dataset_a
                    AND a.value_num IS NOT NULL
                    AND a.value_num >= th.threshold
                    AND b.value_num < th.threshold
            )
            INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
            SELECT CAST(:new_id AS UUID), cc.dggid, 0, 'contour',
                   cc.threshold, 'Contour', jsonb_build_object('level', cc.level_idx, 'value', cc.value_num)
            FROM contour_cells cc
            ON CONFLICT (dataset_id, dggid, tid, attr_key) DO UPDATE SET
                value_num = EXCLUDED.value_num,
                value_json = EXCLUDED.value_json
        """), {"new_id": new_id, "dataset_a": dataset_a, "num_levels": num_levels})

    async def _execute_idw_interpolation(self, new_id: str, dataset_a: str, radius: int):
        """Inverse Distance Weighting interpolation: fill empty neighbor cells
        with weighted average of nearby measured values.
        Weight = 1 / distance^2 where distance = K-ring hop count."""
        await self.db.execute(text("""
            WITH RECURSIVE measured AS (
                SELECT DISTINCT dggid, value_num
                FROM cell_objects
                WHERE dataset_id = :dataset_a AND value_num IS NOT NULL
            ),
            kring AS (
                SELECT m.dggid AS source, m.dggid AS target, 0 AS depth, m.value_num
                FROM measured m
                UNION
                SELECT k.source, t.neighbor_dggid, k.depth + 1, k.value_num
                FROM kring k
                JOIN dgg_topology t ON k.target = t.dggid
                WHERE k.depth < :radius
            ),
            unmeasured_neighbors AS (
                SELECT k.target AS dggid,
                       SUM(k.value_num / POWER(GREATEST(k.depth, 1), 2)) AS weighted_sum,
                       SUM(1.0 / POWER(GREATEST(k.depth, 1), 2)) AS weight_total,
                       COUNT(DISTINCT k.source) AS source_count
                FROM kring k
                WHERE k.depth > 0
                    AND NOT EXISTS (SELECT 1 FROM measured m WHERE m.dggid = k.target)
                GROUP BY k.target
                HAVING COUNT(DISTINCT k.source) >= 2
            )
            INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
            SELECT CAST(:new_id AS UUID), u.dggid, 0, 'interpolated',
                   u.weighted_sum / NULLIF(u.weight_total, 0),
                   'IDW', jsonb_build_object('sources', u.source_count, 'method', 'idw')
            FROM unmeasured_neighbors u
            ON CONFLICT (dataset_id, dggid, tid, attr_key) DO UPDATE SET
                value_num = EXCLUDED.value_num,
                value_json = EXCLUDED.value_json
        """), {"new_id": new_id, "dataset_a": dataset_a, "radius": radius})
