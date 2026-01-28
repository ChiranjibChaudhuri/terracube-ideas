from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from typing import Optional, Literal, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.db import get_db
from app.models import CellObject, Dataset
from app.auth import get_current_user
import uuid

router = APIRouter(prefix="/api/ops", tags=["operations"])

class QueryRequest(BaseModel):
    type: Literal["range", "filter", "aggregate"]
    datasetId: str
    key: str
    min: Optional[float] = None
    max: Optional[float] = None
    op: Optional[str] = None
    value: Optional[Any] = None
    agg: Optional[str] = None
    groupBy: Optional[str] = None
    limit: Optional[int] = 5000

class SpatialRequest(BaseModel):
    type: Literal["intersection", "zonal", "union", "difference", "buffer", "aggregate", "propagate"]
    datasetAId: str
    datasetBId: Optional[str] = None
    keyA: str
    keyB: Optional[str] = None
    tid: Optional[int] = None
    limit: Optional[int] = 1000

def _parse_uuid(value: str, label: str):
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {label}")

def _coerce_number(value: Any):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None

@router.post("/query")
async def run_query(request: QueryRequest = Body(...), db: AsyncSession = Depends(get_db)):
    dataset_id = _parse_uuid(request.datasetId, "datasetId")
    limit = min(max(request.limit or 1, 1), 5000)

    if request.type == "range":
        if request.min is None and request.max is None:
            raise HTTPException(status_code=400, detail="Provide min or max for range query.")

        stmt = select(
            CellObject.dggid,
            CellObject.tid,
            CellObject.attr_key,
            CellObject.value_text,
            CellObject.value_num,
            CellObject.value_json,
        ).where(
            CellObject.dataset_id == dataset_id,
            CellObject.attr_key == request.key,
        )

        if request.min is not None:
            stmt = stmt.where(CellObject.value_num >= request.min)
        if request.max is not None:
            stmt = stmt.where(CellObject.value_num <= request.max)

        stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return {"rows": [dict(row) for row in result.mappings().all()]}

    if request.type == "filter":
        if request.op not in ("eq", None):
            raise HTTPException(status_code=400, detail="Only 'eq' filter is supported.")
        if request.value is None:
            raise HTTPException(status_code=400, detail="Provide a value for filter.")

        numeric_value = _coerce_number(request.value)
        stmt = select(
            CellObject.dggid,
            CellObject.tid,
            CellObject.attr_key,
            CellObject.value_text,
            CellObject.value_num,
            CellObject.value_json,
        ).where(
            CellObject.dataset_id == dataset_id,
            CellObject.attr_key == request.key,
        )

        if numeric_value is not None:
            stmt = stmt.where(CellObject.value_num == numeric_value)
        else:
            stmt = stmt.where(CellObject.value_text == str(request.value))

        stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return {"rows": [dict(row) for row in result.mappings().all()]}

    if request.type == "aggregate":
        if request.groupBy and request.groupBy != "dggid":
            raise HTTPException(status_code=400, detail="Only groupBy=dggid is supported.")
        agg = (request.agg or "avg").lower()
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
            raise HTTPException(status_code=400, detail=f"Unsupported aggregation: {request.agg}")

        value_col = agg_fn(CellObject.value_num).label("value")
        stmt = (
            select(CellObject.dggid.label("dggid"), value_col)
            .where(CellObject.dataset_id == dataset_id, CellObject.attr_key == request.key)
            .group_by(CellObject.dggid)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return {"rows": [dict(row) for row in result.mappings().all()]}

    raise HTTPException(status_code=400, detail="Unsupported query type.")

def _range_from_metadata(metadata: Optional[dict]):
    if not metadata:
        return None
    try:
        return {
            "min": metadata.get("min_level"),
            "max": metadata.get("max_level"),
        }
    except AttributeError:
        return None

def _ranges_overlap(a: Optional[dict], b: Optional[dict]):
    if not a or not b:
        return True
    if a.get("min") is None or a.get("max") is None or b.get("min") is None or b.get("max") is None:
        return True
    return max(a["min"], b["min"]) <= min(a["max"], b["max"])

@router.post("/spatial")
async def run_spatial(request: SpatialRequest = Body(...), db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    dataset_a = _parse_uuid(request.datasetAId, "datasetAId")
    dataset_b = _parse_uuid(request.datasetBId, "datasetBId") if request.datasetBId else None
    
    limit = min(max(request.limit or 1, 1), 50000) # Higher limit for persistence

    ids_to_fetch = [dataset_a]
    if dataset_b:
        ids_to_fetch.append(dataset_b)

    result = await db.execute(select(Dataset).where(Dataset.id.in_(ids_to_fetch)))
    datasets = {str(ds.id): ds for ds in result.scalars().all()}

    if str(dataset_a) not in datasets:
        raise HTTPException(status_code=404, detail="Dataset A not found")
    if dataset_b and str(dataset_b) not in datasets:
        raise HTTPException(status_code=404, detail="Dataset B not found")

    ds_a = datasets[str(dataset_a)]
    ds_b = datasets.get(str(dataset_b)) if dataset_b else None

    if ds_b and ds_a.dggs_name != ds_b.dggs_name:
        raise HTTPException(status_code=409, detail="DGGS mismatch between datasets.")

    # Create new result dataset
    new_id = uuid.uuid4()
    op_name = request.type.capitalize()
    
    desc = f"{op_name} of {ds_a.name}"
    if ds_b:
        desc += f" and {ds_b.name}"

    parents = [str(dataset_a)]
    if dataset_b:
        parents.append(str(dataset_b))

    new_dataset = Dataset(
        id=new_id,
        name=f"{op_name} Result",
        description=desc,
        dggs_name=ds_a.dggs_name,
        metadata_={"source": "spatial_op", "type": request.type, "parents": parents},
        status="processing" # Will update to ready
    )
    db.add(new_dataset)
    await db.commit() # Commit to get ID ready

    try:
        if request.type == "intersection":
            sql = text(
                """
                INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
                SELECT :new_id, a.dggid, a.tid, 'intersection', 
                       CASE WHEN a.value_num IS NOT NULL AND b.value_num IS NOT NULL THEN (a.value_num + b.value_num)/2 ELSE COALESCE(a.value_num, b.value_num) END,
                       'Intersection',
                       jsonb_build_object('a', a.value_json, 'b', b.value_json)
                FROM cell_objects a
                JOIN cell_objects b ON a.dggid = b.dggid
                WHERE a.dataset_id = :dataset_a AND b.dataset_id = :dataset_b
                """
            )
            await db.execute(sql, {"new_id": new_id, "dataset_a": dataset_a, "dataset_b": dataset_b})
        
        elif request.type == "union":
            # Union: Items in A OR B. 
            # We insert A, then insert B (ignoring duplicates or handling them).
            # Simple approach: A UNION B (distinct dggids)
            # But we need values.
            # Strategy: Insert A, then Insert B where not in A?
            # Or just Insert all and let DB handle? cell_objects PK is (dataset_id, dggid, tid, attr_key)? No, usually just ID.
            # Assuming we want unique cells.
            
            # Insert A
            await db.execute(text("""
                INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
                SELECT :new_id, dggid, tid, attr_key, value_num, value_text, value_json
                FROM cell_objects WHERE dataset_id = :dataset_a
            """), {"new_id": new_id, "dataset_a": dataset_a})
            
            # Insert B where not exists in A (spatial union, attribute preservation is tricky, we just take B's attributes for B-only cells, and ignore overlaps? Or overwrite?)
            # Valid Union in GIS usually merges attributes.
            # Simplest for now: Insert B where dggid not in (Select dggid from A)
            await db.execute(text("""
                INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
                SELECT :new_id, dggid, tid, attr_key, value_num, value_text, value_json
                FROM cell_objects b
                WHERE dataset_id = :dataset_b
                AND NOT EXISTS (SELECT 1 FROM cell_objects a WHERE a.dataset_id = :dataset_a AND a.dggid = b.dggid)
            """), {"new_id": new_id, "dataset_a": dataset_a, "dataset_b": dataset_b})

        elif request.type == "difference":
            # Difference: A - B (Cells in A that are NOT in B)
            await db.execute(text("""
                INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
                SELECT :new_id, a.dggid, a.tid, a.attr_key, a.value_num, a.value_text, a.value_json
                FROM cell_objects a
                LEFT JOIN cell_objects b ON a.dggid = b.dggid AND b.dataset_id = :dataset_b
                WHERE a.dataset_id = :dataset_a AND b.dggid IS NULL
            """), {"new_id": new_id, "dataset_a": dataset_a, "dataset_b": dataset_b})

        elif request.type == "buffer":
            # Buffer: K-Ring neighbors using dgg_topology
            # Recursive CTE to find neighbors up to K hops
            iterations = request.limit if request.limit else 1
            iterations = min(iterations, 5) # Cap iterations for safety
            
            await db.execute(text("""
                WITH RECURSIVE bfs AS (
                    SELECT dggid, 0 as depth FROM cell_objects WHERE dataset_id = :dataset_a
                    UNION
                    SELECT t.neighbor_dggid, bfs.depth + 1
                    FROM bfs
                    JOIN dgg_topology t ON bfs.dggid = t.dggid
                    WHERE bfs.depth < :iterations
                )
                INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
                SELECT DISTINCT CAST(:new_id AS UUID), b.dggid, 0, 'buffer', CAST(NULL AS FLOAT), 'Buffer', CAST(NULL AS JSONB)
                FROM bfs b
            """), {"new_id": new_id, "dataset_a": dataset_a, "iterations": iterations})

        elif request.type == "aggregate":
            # Aggregate: Move to parent level
            # We join with topology to get parent, then group by parent
            # Aggregation function: Mean of value_num
            await db.execute(text("""
                INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
                SELECT CAST(:new_id AS UUID), t.parent_dggid, 0, 'aggregate', AVG(a.value_num), 'Aggregated', CAST(NULL AS JSONB)
                FROM cell_objects a
                JOIN dgg_topology t ON a.dggid = t.dggid
                WHERE a.dataset_id = :dataset_a
                AND t.parent_dggid IS NOT NULL
                GROUP BY t.parent_dggid
            """), {"new_id": new_id, "dataset_a": dataset_a})

        elif request.type == "propagate":
            # Propagate: Iterative Buffer with CONDITION (Simple Flood Fill)
            # Use a slightly different CTE that includes a check on the *neighbor's* value?
            # Actually, "Propagate" usually means spreading from source *through* a "friction" or "mask" dataset.
            # But here we might just do "Spread N steps" which is Buffer.
            # Let's implement "Constrained Buffer": Expand only into cells that exist in Dataset B (Mask)
            # Or if Dataset B is not provided, expand everywhere (Buffer).
            
            # Implementation:
            # If dataset_b is provided: Only include neighbor dggid IF it exists in dataset_b (AND optionally satisfy criteria?)
            # Simplified: Intersection of (Buffer A) and B
            # But iterative: Step 1: A.neighbors n B. Step 2: (Result1).neighbors n B ...
            
            iterations = request.limit if request.limit else 5
            iterations = min(iterations, 20)
            
            if dataset_b:
                # Constrained propagation
                await db.execute(text("""
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
                    SELECT DISTINCT CAST(:new_id AS UUID), s.dggid, 0, 'propagate', CAST(NULL AS FLOAT), 'Spread', CAST(NULL AS JSONB)
                    FROM spread s
                """), {"new_id": new_id, "dataset_a": dataset_a, "dataset_b": dataset_b, "iterations": iterations})
            else:
                 # Just Buffer if no mask
                 await db.execute(text("""
                    WITH RECURSIVE bfs AS (
                        SELECT dggid, 0 as depth FROM cell_objects WHERE dataset_id = :dataset_a
                        UNION
                        SELECT t.neighbor_dggid, bfs.depth + 1
                        FROM bfs
                        JOIN dgg_topology t ON bfs.dggid = t.dggid
                        WHERE bfs.depth < :iterations
                    )
                    INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text, value_json)
                    SELECT DISTINCT CAST(:new_id AS UUID), b.dggid, 0, 'buffer', CAST(NULL AS FLOAT), 'Buffer', CAST(NULL AS JSONB)
                    FROM bfs b
                """), {"new_id": new_id, "dataset_a": dataset_a, "iterations": iterations})

        # Update status
        new_dataset.status = "ready"
        await db.commit()
        return {"status": "success", "newDatasetId": str(new_id)}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

