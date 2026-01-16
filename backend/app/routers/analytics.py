from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.repositories.cell_object_repo import CellObjectRepository
from app.auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

class QueryRequest(BaseModel):
    operation: str  # "intersection", "union", "difference"
    dataset_ids: List[str]
    viewport_dggids: Optional[List[str]] = None

@router.post("/query")
async def execute_query(request: QueryRequest = Body(...), db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    if len(request.dataset_ids) < 2:
        raise HTTPException(status_code=400, detail="At least two datasets required for set operations")
        
    try:
        repo = CellObjectRepository(db)
        # Pass the viewport_dggids to the repository
        dggids = await repo.execute_set_operation(
            request.operation, 
            request.dataset_ids, 
            dggid_filter=request.viewport_dggids
        )
        
        return {
            "operation": request.operation, 
            "result_count": len(dggids),
            "dggids": dggids
        }
    except ValueError as ve:
         raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
