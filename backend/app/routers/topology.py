from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from typing import Optional
from app.dggal_utils import get_dggal_service
from app.auth import get_current_user

router = APIRouter(prefix="/api/ops", tags=["topology"])

class SpatialOpRequest(BaseModel):
    type: str
    dggid: str
    dggsName: Optional[str] = None

@router.post("/topology")
async def handle_topology_op(request: SpatialOpRequest = Body(...)):
    service = get_dggal_service(request.dggsName or "IVEA3H")
    
    try:
        if request.type == "neighbors":
            neighbors = service.get_neighbors(request.dggid)
            return {"dggid": request.dggid, "neighbors": neighbors}
            
        elif request.type == "parent":
            parent = service.get_parent(request.dggid)
            return {"dggid": request.dggid, "parent": parent}
            
        elif request.type == "children":
            children = service.get_children(request.dggid)
            return {"dggid": request.dggid, "children": children}
            
        elif request.type == "vertices":
            vertices = service.get_vertices(request.dggid)
            return {"dggid": request.dggid, "vertices": vertices}
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown operation type: {request.type}")
            
    except Exception as e:
        # Catch internal dggal errors or value errors
        raise HTTPException(status_code=500, detail=str(e))
