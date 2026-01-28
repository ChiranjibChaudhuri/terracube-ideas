from fastapi import APIRouter, Depends, Form, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db
from app.repositories.dataset_repo import DatasetRepository
from app.models import Dataset, CellObject
from app.auth import get_current_user, get_optional_user
from pydantic import BaseModel
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
