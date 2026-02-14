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
        valid_ops = {"intersection", "union", "difference", "buffer", "aggregate", "propagate"}
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
        topology_ops = {"buffer", "aggregate", "propagate"}
        if op_type in topology_ops:
            topology_check = await self.db.execute(text(
                "SELECT 1 FROM dgg_topology LIMIT 1"
            ))
            if topology_check.scalar() == 0:
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
                    await self._execute_aggregate(new_id, dataset_a)

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
                    AND COALESCE(a.tid, b.tid)
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

    async def _execute_aggregate(self, new_id: str, dataset_a: str):
        """Aggregate: coarsen by moving to parent cells using topology table"""
        await self.db.execute(text("""
            INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
            SELECT CAST(:new_id AS UUID), t.parent_dggid, 0, 'aggregate',
                   AVG(a.value_num), 'Aggregated', CAST(NULL AS JSONB)
            FROM cell_objects a
            JOIN dgg_topology t ON a.dggid = t.dggid
            WHERE a.dataset_id = :dataset_a
            AND t.parent_dggid IS NOT NULL
            GROUP BY t.parent_dggid
        """), {"new_id": new_id, "dataset_a": dataset_a})

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
        """), {"new_id": new_id, "dataset_a": dataset_a, "dataset_b": dataset_b, "iterations": iterations}
