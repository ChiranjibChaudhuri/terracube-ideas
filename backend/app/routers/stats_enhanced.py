"""
Enhanced Statistics Router for TerraCube IDEAS

Provides comprehensive zonal statistics, correlation analysis,
and hotspot detection for DGGS datasets.
"""

from fastapi import APIRouter, HTTPException, Body, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.services.zonal_stats import get_zonal_stats_service, StatisticMethod
from app.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats", tags=["statistics"])


class ZonalStatsRequest(BaseModel):
    dataset_id: str
    mask_dataset_id: Optional[str] = None
    variables: List[str] = Field(..., description="Attribute keys to analyze")
    operations: Optional[List[str]] = Field(
        None,
        description="Statistics to compute (default: all)"
    )
    percentile_bins: Optional[List[int]] = Field(
        [25, 50, 75, 90],
        description="Percentile bins to compute"
    )
    histogram_bins: int = Field(10, ge=1, le=50, description="Number of histogram bins")
    weight_by_area: bool = Field(False, description="Weight statistics by cell area")


class CorrelationRequest(BaseModel):
    dataset_id: str
    mask_dataset_id: Optional[str] = None
    variables: List[str] = Field(..., min_length=2, description="Variables to correlate")
    method: Literal["pearson", "spearman"] = "pearson"


class HotspotRequest(BaseModel):
    dataset_id: str
    mask_dataset_id: Optional[str] = None
    variable: str = Field(..., description="Variable to analyze")
    radius: int = Field(3, ge=1, le=10, description="K-ring radius for hotspot analysis")
    method: Literal["getis_ord", "kernel"] = Field("getis_ord", description="Hotspot method")


@router.post("/zonal")
async def zonal_statistics(
    request: ZonalStatsRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Enhanced zonal statistics supporting multiple variables and operations.

    Operations:
    - sum, mean, median, min, max, stddev, variance, count
    - mode (most frequent value)
    - percentiles (25th, 50th, 75th, 90th)
    - histogram (with configurable bins)
    """
    service = get_zonal_stats_service(db)

    try:
        result = await service.execute_zonal_stats(
            dataset_id=request.dataset_id,
            mask_dataset_id=request.mask_dataset_id,
            variables=request.variables,
            operations=request.operations,
            percentile_bins=request.percentile_bins,
            histogram_bins=request.histogram_bins,
            weight_by_area=request.weight_by_area
        )
        return {
            "dataset_id": request.dataset_id,
            "mask_dataset_id": request.mask_dataset_id,
            "results": result["results"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Zonal statistics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/correlation")
async def correlation_analysis(
    request: CorrelationRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Compute correlation matrix between multiple variables.

    Returns Pearson correlation coefficients and cell counts
    for all pairs of requested variables.
    """
    service = get_zonal_stats_service(db)

    try:
        result = await service.compute_correlation_matrix(
            dataset_id=request.dataset_id,
            variables=request.variables,
            mask_dataset_id=request.mask_dataset_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Correlation analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hotspot")
async def hotspot_analysis(
    request: HotspotRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Detect spatial hotspots using Getis-Ord Gi* statistics.

    Identifies statistically significant clusters of high/low values.
    Returns cells ordered by statistical significance.
    """
    service = get_zonal_stats_service(db)

    try:
        result = await service.compute_hotspots(
            dataset_id=request.dataset_id,
            variable=request.variable,
            mask_dataset_id=request.mask_dataset_id,
            radius=request.radius,
            method=request.method
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Hotspot analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
