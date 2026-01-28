from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.services.spatial_engine import SpatialEngine
from app.auth import get_current_user

router = APIRouter(
    prefix="/api/toolbox",
    tags=["toolbox"],
    responses={404: {"description": "Not found"}},
)

class BufferRequest(BaseModel):
    dggids: List[str]
    iterations: int = 1
    dggsName: Optional[str] = None

class AggregateRequest(BaseModel):
    dggids: List[str]
    levels: int = 1
    dggsName: Optional[str] = None

class ExpandRequest(BaseModel):
    dggids: List[str]
    iterations: int = 1
    dggsName: Optional[str] = None

class MaskRequest(BaseModel):
    source_dggids: List[str]
    mask_dggids: List[str]

@router.post("/buffer")
async def buffer_op(request: BufferRequest, user: dict = Depends(get_current_user)):
    """
    Calculate buffer zones around a set of DGGS cells.
    Returns the expanded set of cell IDs.
    """
    engine = SpatialEngine(request.dggsName or "IVEA3H")
    try:
        result = await engine.buffer(request.dggids, request.iterations)
        return {"result_count": len(result), "dggids": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/aggregate")
async def aggregate_op(request: AggregateRequest, user: dict = Depends(get_current_user)):
    """
    Aggregate cells to a coarser resolution level.
    """
    engine = SpatialEngine(request.dggsName or "IVEA3H")
    try:
        result = await engine.aggregate(request.dggids, request.levels)
        return {"result_count": len(result), "dggids": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/expand")
async def expand_op(request: ExpandRequest, user: dict = Depends(get_current_user)):
    """
    Expand cells to a finer resolution level (children).
    """
    engine = SpatialEngine(request.dggsName or "IVEA3H")
    try:
        result = await engine.expand(request.dggids, request.iterations)
        return {"result_count": len(result), "dggids": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SetOpRequest(BaseModel):
    set_a: List[str]
    set_b: List[str]

@router.post("/union")
async def union_op(request: SetOpRequest, user: dict = Depends(get_current_user)):
    """
    Compute the set union of two cell lists (in-memory).
    """
    engine = SpatialEngine()
    try:
        result = engine.union(request.set_a, request.set_b)
        return {"result_count": len(result), "dggids": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/intersection")
async def intersection_op(request: SetOpRequest, user: dict = Depends(get_current_user)):
    """
    Compute the set intersection of two cell lists (in-memory).
    """
    engine = SpatialEngine()
    try:
        result = engine.intersection(request.set_a, request.set_b)
        return {"result_count": len(result), "dggids": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/difference")
async def difference_op(request: SetOpRequest, user: dict = Depends(get_current_user)):
    """
    Compute the set difference (A - B) of two cell lists (in-memory).
    """
    engine = SpatialEngine()
    try:
        result = engine.difference(request.set_a, request.set_b)
        return {"result_count": len(result), "dggids": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mask")
async def mask_op(request: MaskRequest, user: dict = Depends(get_current_user)):
    """
    Filter source cells, keeping only those present in the mask set.
    """
    engine = SpatialEngine()
    try:
        result = engine.mask(request.source_dggids, request.mask_dggids)
        return {"result_count": len(result), "dggids": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
