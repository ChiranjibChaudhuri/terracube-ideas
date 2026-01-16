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

class AggregateRequest(BaseModel):
    dggids: List[str]

class MaskRequest(BaseModel):
    source_dggids: List[str]
    mask_dggids: List[str]

@router.post("/buffer")
async def buffer_op(request: BufferRequest):
    engine = SpatialEngine()
    try:
        result = await engine.buffer(request.dggids, request.iterations)
        return {"result_count": len(result), "dggids": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/aggregate")
async def aggregate_op(request: AggregateRequest):
    engine = SpatialEngine()
    try:
        result = await engine.aggregate(request.dggids)
        return {"result_count": len(result), "dggids": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SetOpRequest(BaseModel):
    set_a: List[str]
    set_b: List[str]

@router.post("/union")
async def union_op(request: SetOpRequest):
    engine = SpatialEngine()
    try:
        result = engine.union(request.set_a, request.set_b)
        return {"result_count": len(result), "dggids": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/intersection")
async def intersection_op(request: SetOpRequest):
    engine = SpatialEngine()
    try:
        result = engine.intersection(request.set_a, request.set_b)
        return {"result_count": len(result), "dggids": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/difference")
async def difference_op(request: SetOpRequest):
    engine = SpatialEngine()
    try:
        result = engine.difference(request.set_a, request.set_b)
        return {"result_count": len(result), "dggids": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mask")
async def mask_op(request: MaskRequest):
    engine = SpatialEngine()
    try:
        result = engine.mask(request.source_dggids, request.mask_dggids)
        return {"result_count": len(result), "dggids": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
