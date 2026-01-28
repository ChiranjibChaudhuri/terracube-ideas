from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from typing import Optional, List
from app.dggal_utils import get_dggal_service
from app.auth import get_current_user

router = APIRouter(prefix="/api/ops", tags=["topology"])

class SpatialOpRequest(BaseModel):
    type: str
    dggid: str
    dggsName: Optional[str] = None

class ListZonesRequest(BaseModel):
    level: int
    bbox: List[float]  # [min_lat, min_lon, max_lat, max_lon]
    dggsName: Optional[str] = None
    maxZones: Optional[int] = 3000

@router.post("/list_zones")
async def list_zones(request: ListZonesRequest = Body(...)):
    """
    List zone IDs for a given bounding box and level.
    This ensures frontend uses the same zone IDs that backend stores.
    """
    if len(request.bbox) != 4:
        raise HTTPException(status_code=400, detail="bbox must have 4 elements: [min_lat, min_lon, max_lat, max_lon]")
    
    max_level = 20
    if request.level < 0 or request.level > max_level:
        raise HTTPException(status_code=400, detail=f"level must be between 0 and {max_level}")
    
    service = get_dggal_service(request.dggsName or "IVEA3H")
    
    try:
        zones = service.list_zones_bbox(request.level, request.bbox)
        # Limit to prevent overwhelming response
        max_zones = min(request.maxZones or 3000, 5000)
        if len(zones) > max_zones:
            zones = zones[:max_zones]
        return {"level": request.level, "zoneCount": len(zones), "zones": zones}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/topology")
async def handle_topology_op(request: SpatialOpRequest = Body(...)):
    """
    Perform low-level topology lookups for a single cell.
    
    - **type**: Operation type (neighbors, parent, children, vertices)
    - **dggid**: The target DGGS ID
    """
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
