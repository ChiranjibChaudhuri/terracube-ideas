from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.services.high_vibe_service import HighVibeService
from typing import Optional

router = APIRouter(prefix="/api/high-vibes", tags=["high-vibes"])

@router.get("/zones/{zone_id}/data")
async def get_zone_data(
    zone_id: str,
    dataset_id: str = Query(..., description="UUID of the dataset"),
    depth: int = Query(0, description="Relative depth for subzones"),
    attr_key: Optional[str] = Query(None, description="Attribute key to fetch"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get data for a zone and its subzones in High Vibes format (DGGS-JSON inspired).
    Useful for client-side visualization where geometry is generated locally.
    """
    service = HighVibeService(db)
    try:
        return await service.get_zone_data(zone_id, depth, dataset_id, attr_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
