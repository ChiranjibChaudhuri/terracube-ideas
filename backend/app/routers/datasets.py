from fastapi import APIRouter, Depends, Form, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db
from app.repositories.dataset_repo import DatasetRepository
from app.models import Dataset, CellObject
from app.auth import get_current_user, get_optional_user
from app.validators.datasets import (
    DatasetCreateRequest,
    DatasetUpdateRequest,
    CellLookupRequest,
    CellListRequest,
    DatasetExportRequest,
    SpatialOperationRequest,
    ZonalStatsRequest,
)
from pydantic import BaseModel, ValidationError
from typing import List, Optional
import uuid

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

class LookupRequest(BaseModel):
    dggids: List[str]
    key: Optional[str] = None
    tid: Optional[int] = None

def serialize_dataset(dataset: Dataset):
    return {
        "id": str(dataset.id),
        "name": dataset.name,
        "description": dataset.description,
        "dggs_name": dataset.dggs_name,
        "level": dataset.level,
        "status": dataset.status,
        "metadata": dataset.metadata_ or {},
        "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
    }

@router.get("")
async def list_datasets(search: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """
    List all available datasets, optionally filtered by name.
    """
    stmt = select(Dataset)
    if search:
        # Use parameterized query to prevent SQL injection
        from sqlalchemy import literal
        stmt = stmt.where(Dataset.name.ilike('%' + search + '%'))
    stmt = stmt.order_by(Dataset.created_at.desc())
    result = await db.execute(stmt)
    datasets = [serialize_dataset(ds) for ds in result.scalars().all()]
    return {"datasets": datasets}

@router.get("/{dataset_id}")
async def get_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get detailed metadata for a specific dataset by ID.
    """
    repo = DatasetRepository(db)
    try:
        dataset = await repo.get_by_id(uuid.UUID(dataset_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dataset ID")
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"dataset": serialize_dataset(dataset)}

@router.post("")
async def create_dataset(
    name: str = Form(...), 
    description: str = Form(None),
    level: Optional[int] = Form(None),
    dggs_name: str = Form("IVEA3H"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Create a new empty dataset.
    """
    repo = DatasetRepository(db)
    new_dataset = await repo.create(name=name, description=description, level=level, dggs_name=dggs_name)
    return {"dataset": serialize_dataset(new_dataset)}

@router.get("/{dataset_id}/cells")
async def list_cells(
    dataset_id: str,
    key: Optional[str] = None,
    dggid_prefix: Optional[str] = Query(None, alias="dggidPrefix"),
    tid: Optional[int] = None,
    limit: int = 500,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    try:
        dataset_uuid = uuid.UUID(dataset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dataset ID")

    limit = min(max(limit, 1), 5000)
    offset = max(offset, 0)

    stmt = select(
        CellObject.dggid,
        CellObject.tid,
        CellObject.attr_key,
        CellObject.value_text,
        CellObject.value_num,
        CellObject.value_json,
    ).where(CellObject.dataset_id == dataset_uuid)

    if key:
        stmt = stmt.where(CellObject.attr_key == key)
    if dggid_prefix:
        stmt = stmt.where(CellObject.dggid.like(f"{dggid_prefix}%"))
    if tid is not None:
        stmt = stmt.where(CellObject.tid == tid)

    stmt = stmt.order_by(CellObject.dggid).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return {"cells": [dict(row) for row in result.mappings().all()]}

@router.post("/{dataset_id}/lookup")
async def lookup_cells(
    dataset_id: str,
    request: LookupRequest,
    db: AsyncSession = Depends(get_db)
):
    if not request.dggids:
        raise HTTPException(status_code=400, detail="dggids cannot be empty")
    if len(request.dggids) > 3000:
        raise HTTPException(status_code=400, detail="dggids too large (max 3000)")

    try:
        dataset_uuid = uuid.UUID(dataset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dataset ID")

    stmt = select(
        CellObject.dggid,
        CellObject.tid,
        CellObject.attr_key,
        CellObject.value_text,
        CellObject.value_num,
        CellObject.value_json,
    ).where(
        CellObject.dataset_id == dataset_uuid,
        CellObject.dggid.in_(request.dggids),
    )

    if request.key:
        stmt = stmt.where(CellObject.attr_key == request.key)
    if request.tid is not None:
        stmt = stmt.where(CellObject.tid == request.tid)

    stmt = stmt.order_by(CellObject.dggid)
    result = await db.execute(stmt)
    return {"cells": [dict(row) for row in result.mappings().all()]}

class ExportRequest(BaseModel):
    format: str  # "csv" or "geojson"
    bbox: Optional[List[float]] = None  # Optional bounding box filter

@router.post("/{dataset_id}/export")
async def export_dataset(
    dataset_id: str,
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Export a dataset as CSV or GeoJSON.
    Returns a file download response.
    """
    from fastapi.responses import Response, StreamingResponse
    import csv
    import json
    import io

    try:
        dataset_uuid = uuid.UUID(dataset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dataset ID")

    # Verify dataset exists
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get_by_id(dataset_uuid)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Query cells
    stmt = select(
        CellObject.dggid,
        CellObject.tid,
        CellObject.attr_key,
        CellObject.value_text,
        CellObject.value_num,
        CellObject.value_json,
    ).where(CellObject.dataset_id == dataset_uuid)

    if request.bbox and len(request.bbox) == 4:
        # Filter by bbox if provided (requires vertices lookup)
        # For now, just get all cells - bbox filtering would need dggal integration
        pass

    result = await db.execute(stmt)
    cells = [dict(row) for row in result.mappings().all()]

    if not cells:
        raise HTTPException(status_code=404, detail="No cells found in dataset")

    if request.format.lower() == "csv":
        # Export as CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["dggid", "tid", "attr_key", "value_text", "value_num", "value_json"])

        for cell in cells:
            writer.writerow([
                cell.get("dggid", ""),
                cell.get("tid", ""),
                cell.get("attr_key", ""),
                cell.get("value_text", ""),
                cell.get("value_num", ""),
                json.dumps(cell.get("value_json")) if cell.get("value_json") else ""
            ])

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{dataset.name}_{dataset_id}.csv"'
            }
        )

    elif request.format.lower() == "geojson":
        # Export as GeoJSON (requires DGGAL for vertices)
        # For now, export point-based GeoJSON using centroids
        from app.dggal_utils import get_dggal_service

        dggal = get_dggal_service(dataset.dggs_name or "IVEA3H")

        features = []
        for cell in cells:
            dggid = cell.get("dggid")
            if not dggid:
                continue

            # Get centroid as point geometry
            centroid = dggal.get_centroid(dggid)

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [centroid["lon"], centroid["lat"]]
                },
                "properties": {
                    "dggid": dggid,
                    "tid": cell.get("tid"),
                    "attr_key": cell.get("attr_key"),
                    "value_text": cell.get("value_text"),
                    "value_num": cell.get("value_num")
                }
            }

            # Add value_json to properties if present
            if cell.get("value_json"):
                feature["properties"]["value_json"] = cell.get("value_json")

            features.append(feature)

        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        return Response(
            content=json.dumps(geojson),
            media_type="application/geo+json",
            headers={
                "Content-Disposition": f'attachment; filename="{dataset.name}_{dataset_id}.geojson"'
            }
        )

    else:
        raise HTTPException(status_code=400, detail="Unsupported export format. Use 'csv' or 'geojson'")
