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
    type: Literal["intersection", "zonal"]
    datasetAId: str
    datasetBId: str
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
async def run_spatial(request: SpatialRequest = Body(...), db: AsyncSession = Depends(get_db)):
    dataset_a = _parse_uuid(request.datasetAId, "datasetAId")
    dataset_b = _parse_uuid(request.datasetBId, "datasetBId")
    limit = min(max(request.limit or 1, 1), 5000)

    result = await db.execute(select(Dataset).where(Dataset.id.in_([dataset_a, dataset_b])))
    datasets = {str(ds.id): ds for ds in result.scalars().all()}

    if str(dataset_a) not in datasets or str(dataset_b) not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if datasets[str(dataset_a)].dggs_name != datasets[str(dataset_b)].dggs_name:
        raise HTTPException(status_code=409, detail="DGGS mismatch between datasets.")

    range_a = _range_from_metadata(datasets[str(dataset_a)].metadata_)
    range_b = _range_from_metadata(datasets[str(dataset_b)].metadata_)

    if not _ranges_overlap(range_a, range_b):
        raise HTTPException(
            status_code=409,
            detail="Resolution mismatch: datasets must have overlapping min/max DGGS levels.",
        )

    if request.type == "intersection":
        key_b = request.keyB or request.keyA
        clauses = [
            "a.dataset_id = :dataset_a",
            "b.dataset_id = :dataset_b",
            "a.dggid = b.dggid",
            "a.attr_key = :key_a",
            "b.attr_key = :key_b",
        ]
        params = {
            "dataset_a": dataset_a,
            "dataset_b": dataset_b,
            "key_a": request.keyA,
            "key_b": key_b,
            "limit": limit,
        }
        if request.tid is not None:
            clauses.append("a.tid = :tid")
            clauses.append("b.tid = :tid")
            params["tid"] = request.tid

        sql = text(
            f"""
            SELECT a.dggid, a.value_num AS value_num, a.value_text AS value_text,
                   b.value_num AS value_num_b, b.value_text AS value_text_b
            FROM cell_objects a
            JOIN cell_objects b ON a.dggid = b.dggid
            WHERE {" AND ".join(clauses)}
            LIMIT :limit
            """
        )
        rows = await db.execute(sql, params)
        return {"rows": [dict(row) for row in rows.mappings().all()], "operation": "intersection"}

    if request.type == "zonal":
        key_b = request.keyB or request.keyA
        clauses = [
            "a.dataset_id = :dataset_a",
            "b.dataset_id = :dataset_b",
            "a.attr_key = :key_a",
            "b.attr_key = :key_b",
            "a.dggid = b.dggid",
        ]
        params = {
            "dataset_a": dataset_a,
            "dataset_b": dataset_b,
            "key_a": request.keyA,
            "key_b": key_b,
            "limit": limit,
        }
        if request.tid is not None:
            clauses.append("a.tid = :tid")
            clauses.append("b.tid = :tid")
            params["tid"] = request.tid

        sql = text(
            f"""
            SELECT b.dggid AS dggid, AVG(a.value_num) AS value
            FROM cell_objects a
            JOIN cell_objects b ON a.dggid = b.dggid
            WHERE {" AND ".join(clauses)}
            GROUP BY b.dggid
            LIMIT :limit
            """
        )
        rows = await db.execute(sql, params)
        return {"rows": [dict(row) for row in rows.mappings().all()], "operation": "zonal"}

    raise HTTPException(status_code=400, detail="Unsupported spatial operation type.")
