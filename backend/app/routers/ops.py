from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from typing import Optional, Literal, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.auth import get_current_user
from app.services.ops_service import OpsService
import logging

logger = logging.getLogger(__name__)

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
    type: Literal[
        "intersection", "zonal", "union", "difference", "symmetric_difference",
        "buffer", "buffer_weighted", "aggregate", "propagate",
        "contour", "idw_interpolation"
    ]
    datasetAId: str
    datasetBId: Optional[str] = None
    keyA: str
    keyB: Optional[str] = None
    tid: Optional[int] = None
    limit: Optional[int] = 1000

@router.post("/query")
async def run_query(request: QueryRequest = Body(...), db: AsyncSession = Depends(get_db)):
    """
    Execute a flexible attribute query on the database.
    
    Supports:
    - **range**: Filter by numeric range (min/max)
    - **filter**: Exact match on value
    - **aggregate**: Group by DGGS ID and compute stats (avg, sum, etc.)
    """
    service = OpsService(db)
    try:
        return await service.execute_query(
            dataset_id_str=request.datasetId,
            query_type=request.type,
            key=request.key,
            min_val=request.min,
            max_val=request.max,
            op=request.op,
            value=request.value,
            agg=request.agg,
            group_by=request.groupBy,
            limit=request.limit or 5000
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/spatial")
async def run_spatial(request: SpatialRequest = Body(...), db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    """
    Execute a long-running spatial operation between datasets and store the result.
    
    Operations:
    - **intersection**: Geometric intersection of two datasets
    - **union**: Geometric union
    - **difference**: Geometric difference (A - B)
    - **buffer**: Expand cells by K rings
    - **aggregate**: Coarsen resolution
    - **propagate**: Constrained expansion (flood fill)
    """
    service = OpsService(db)
    try:
        return await service.execute_spatial_op(
            op_type=request.type,
            dataset_a_id=request.datasetAId,
            dataset_b_id=request.datasetBId,
            limit=request.limit or 1000
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
         logger.error(f"Spatial Op error: {e}")
         raise HTTPException(status_code=500, detail=str(e))

