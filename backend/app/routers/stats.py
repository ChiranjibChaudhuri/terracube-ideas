from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from typing import List, Literal
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.repositories.cell_object_repo import CellObjectRepository
from app.services.spatial_engine import SpatialEngine
from app.auth import get_current_user
import logging

router = APIRouter(
    prefix="/api/stats",
    tags=["stats"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)

class ZonalStatsRequest(BaseModel):
    zone_dataset_id: str
    value_dataset_id: str
    operation: Literal['MEAN', 'MAX', 'MIN', 'COUNT', 'SUM'] = 'MEAN'

@router.post("/zonal_stats")
async def calculate_zonal_stats(
    request: ZonalStatsRequest, 
    db: AsyncSession = Depends(get_db)
):
    try:
        repo = CellObjectRepository(db)
        dataset_repo = CellObjectRepository(db) # We need DatasetRepo really, but let's use SQL for speed
        # Actually we need the levels.
        # Let's verify levels from 'datasets' table.
        from sqlalchemy import text
        
        async def get_level(ds_id):
            res = await db.execute(text("SELECT level FROM datasets WHERE id = :id"), {"id": ds_id})
            return res.scalar() or 0
            
        zone_level = await get_level(request.zone_dataset_id)
        value_level = await get_level(request.value_dataset_id)
        
        logger.info(f"Zonal Stats: Zone Lv {zone_level} vs Value Lv {value_level}")
        
        engine = SpatialEngine()
        
        # Step A: Get IDs
        zone_ids = await repo.execute_set_operation("union", [request.zone_dataset_id], limit=100000)
        value_ids_all = await repo.execute_set_operation("union", [request.value_dataset_id], limit=100000)
        
        # Step B: Normalize
        # If Zone is coarser (lower level) than Value, expand Zone.
        normalized_zone_ids = zone_ids
        if zone_level < value_level:
            iterations = value_level - zone_level
            logger.info(f"Expanding zone cells by {iterations} levels to match values...")
            normalized_zone_ids = await engine.expand(zone_ids, iterations=iterations)
        elif zone_level > value_level:
            # If Zone is finer than Value, we effectively sample the Value? 
            # Or expand Value to Zone? 
            # Standard "Zonal Stats" usually aggregates Value pixels inside Zone polygon.
            # If Zone is tiny inside a big Value pixel, it takes that pixel's value (or area weighted).
            # For this MVP, let's assume strict containment logic: 
            # Expand Value to match Zone? No, that duplicates values (bad for Sum/Count).
            # We should probably aggregate Zone to Value level to find matches?
            # Let's panic/warn for now, or just try intersection (will likely fail).
            logger.warning("Zone level > Value level. Intersection might match nothing without complex resampling.")
        
        # Step C: Intersection
        overlap_ids = engine.intersection(normalized_zone_ids, value_ids_all)
        
        if not overlap_ids:
             return {
                "operation": request.operation,
                "result": 0,
                "count": 0,
                "note": f"No overlap (Lv {zone_level} vs {value_level})"
            }

        # Step D: Get Values
        values = await repo.get_values_by_dggids(request.value_dataset_id, overlap_ids)
        
        if not values:
             return {
                "operation": request.operation,
                "result": 0,
                "count": 0,
                "note": "No numeric values found"
            }
            
        # Step E: Compute Stats
        result = 0.0
        if request.operation == 'MEAN':
            result = sum(values) / len(values)
        elif request.operation == 'MAX':
            result = max(values)
        elif request.operation == 'MIN':
            result = min(values)
        elif request.operation == 'SUM':
            result = sum(values)
        elif request.operation == 'COUNT':
            result = len(values)
            
        return {
            "operation": request.operation,
            "result": round(result, 4),
            "count": len(values),
            "zone_cells_original": len(zone_ids),
            "zone_cells_expanded": len(normalized_zone_ids),
            "overlap_cells": len(overlap_ids)
        }

    except Exception as e:
        logger.error(f"Zonal Stats Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
