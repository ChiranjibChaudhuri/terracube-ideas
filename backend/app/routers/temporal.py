"""
Temporal Operations Router for TerraCube IDEAS

Provides endpoints for temporal queries, time series extraction,
and cellular automata modeling.
"""

from fastapi import APIRouter, HTTPException, Body, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.services.temporal import (
    get_temporal_service,
    get_ca_service,
    TemporalOperation,
    TemporalGranularity
)
from app.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/temporal", tags=["temporal", "ca"])


class TemporalSnapshotRequest(BaseModel):
    dataset_id: str = Field(..., description="Source dataset")
    target_tid: int = Field(..., ge=0, le=9, description="Target temporal resolution level (0-9)")
    target_timestamp: Optional[str] = Field(None, description="ISO timestamp for snapshot")


class TemporalRangeRequest(BaseModel):
    dataset_id: str = Field(..., description="Source dataset")
    start_tid: int = Field(..., ge=0, le=9, description="Starting temporal level")
    end_tid: int = Field(..., ge=0, le=9, description="Ending temporal level")
    start_value: Optional[int] = Field(None, description="Starting value at start level")
    end_value: Optional[int] = Field(None, description="Ending value at end level")
    attributes: Optional[List[str]] = Field(None, description="Attributes to include")


class TemporalAggregateRequest(BaseModel):
    dataset_id: str = Field(..., description="Source dataset")
    source_tid: int = Field(..., ge=0, le=9, description="Source temporal level")
    target_tid: int = Field(..., ge=0, le=9, description="Target temporal level (must be >= source)")
    agg_method: str = Field("mean", description="Aggregation method: mean, sum, min, max, first, last")


class TemporalDifferenceRequest(BaseModel):
    dataset_a_id: str = Field(..., description="First dataset (earlier time)")
    dataset_b_id: str = Field(..., description="Second dataset (later time)")
    tid_a: int = Field(..., description="Temporal level for dataset A")
    tid_b: int = Field(..., description="Temporal level for dataset B")


class TimeSeriesRequest(BaseModel):
    dataset_id: str = Field(..., description="Source dataset")
    dggid: str = Field(..., description="Cell identifier")
    attr_key: str = Field(..., description="Attribute to extract")
    start_tid: Optional[int] = Field(None, ge=0, le=9, description="Starting temporal level")
    end_tid: Optional[int] = Field(None, ge=0, le=9, description="Ending temporal level")


class CAStepRequest(BaseModel):
    model_id: str = Field(..., description="CA model ID")
    current_state_dataset_id: str = Field(..., description="Current state dataset")


class CARunRequest(BaseModel):
    model_id: str = Field(..., description="CA model ID")
    initial_state_dataset_id: str = Field(..., description="Initial state dataset")
    iterations: int = Field(10, ge=1, le=100, description="Number of timesteps")
    mask_dataset_id: Optional[str] = Field(None, description="Optional mask for constrained propagation")


@router.get("/hierarchy")
async def get_temporal_hierarchy(
    db: AsyncSession = Depends(get_db)
):
    """
    Return temporal hierarchy levels from IDEAS data model.

    T0: Instantaneous (single moment)
    T1-T9: Progressively coarser time resolutions

    Returns level definitions with descriptions.
    """
    service = get_temporal_service(db)

    try:
        result = await service.get_temporal_hierarchy()
        return result
    except Exception as e:
        logger.error(f"Error getting temporal hierarchy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshot")
async def temporal_snapshot(
    request: TemporalSnapshotRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Get temporal snapshot at a specific time resolution.

    - **dataset_id**: Source dataset
    - **target_tid**: Target temporal resolution level (0-9)
    - **target_timestamp**: Optional specific timestamp
    """
    service = get_temporal_service(db)

    try:
        result = await service.temporal_snapshot(
            dataset_id=request.dataset_id,
            target_tid=request.target_tid,
            target_timestamp=request.target_timestamp
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating temporal snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/range")
async def temporal_range(
    request: TemporalRangeRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Extract temporal range/slice from a dataset.

    - **dataset_id**: Source dataset
    - **start_tid**: Starting temporal level
    - **end_tid**: Ending temporal level
    - **start_value**: Optional starting value
    - **end_value**: Optional ending value
    - **attributes**: Optional attributes to include
    """
    service = get_temporal_service(db)

    try:
        result = await service.temporal_range(
            dataset_id=request.dataset_id,
            start_tid=request.start_tid,
            end_tid=request.end_tid,
            start_value=request.start_value,
            end_value=request.end_value,
            attributes=request.attributes
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error extracting temporal range: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/aggregate")
async def temporal_aggregate(
    request: TemporalAggregateRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Aggregate temporal data to coarser resolution.

    Creates a new dataset with aggregated temporal values.

    - **dataset_id**: Source dataset
    - **source_tid**: Source temporal level
    - **target_tid**: Target temporal level (must be >= source)
    - **agg_method**: Aggregation method (mean, sum, min, max, first, last)
    """
    service = get_temporal_service(db)

    try:
        result = await service.temporal_aggregate(
            dataset_id=request.dataset_id,
            source_tid=request.source_tid,
            target_tid=request.target_tid,
            agg_method=request.agg_method
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error aggregating temporally: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/difference")
async def temporal_difference(
    request: TemporalDifferenceRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Compute temporal difference between two datasets.

    Returns cells that changed between temporal states.

    - **dataset_a_id**: First dataset (earlier time)
    - **dataset_b_id**: Second dataset (later time)
    - **tid_a**: Temporal level for dataset A
    - **tid_b**: Temporal level for dataset B
    """
    service = get_temporal_service(db)

    try:
        result = await service.temporal_difference(
            dataset_a_id=request.dataset_a_id,
            dataset_b_id=request.dataset_b_id,
            tid_a=request.tid_a,
            tid_b=request.tid_b
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error computing temporal difference: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/timeseries")
async def get_timeseries(
    request: TimeSeriesRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Extract time series for a specific cell and attribute.

    - **dataset_id**: Source dataset
    - **dggid**: Cell identifier
    - **attr_key**: Attribute to extract
    - **start_tid**: Optional starting temporal level
    - **end_tid**: Optional ending temporal level
    """
    service = get_temporal_service(db)

    try:
        result = await service.get_timeseries(
            dataset_id=request.dataset_id,
            dggid=request.dggid,
            attr_key=request.attr_key,
            start_tid=request.start_tid,
            end_tid=request.end_tid
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error extracting time series: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Cellular Automata endpoints

@router.post("/ca/initialize")
async def initialize_ca_model(
    dataset_id: str = Body(..., embed=True),
    state_attr: str = Body("state", embed=True),
    rules: Optional[Dict[str, Any]] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Initialize Cellular Automata model from dataset.

    - **dataset_id**: Source dataset with initial states
    - **state_attr**: Attribute containing cell states
    - **rules**: Optional CA rule configuration
    """
    service = get_ca_service(db)

    try:
        result = await service.initialize_ca_model(
            dataset_id=dataset_id,
            state_attr=state_attr,
            rules=rules
        )
        return {
            "model_id": result,
            "dataset_id": dataset_id,
            "state_attr": state_attr
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error initializing CA model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ca/step")
async def ca_step(
    request: CAStepRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Execute one CA timestep.

    - **model_id**: CA model ID
    - **current_state_dataset_id**: Current state dataset
    """
    service = get_ca_service(db)

    try:
        result = await service.ca_step(
            model_id=request.model_id,
            current_state_dataset_id=request.current_state_dataset_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error executing CA step: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ca/run")
async def ca_run(
    request: CARunRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Run CA simulation for N timesteps.

    - **model_id**: CA model ID
    - **initial_state_dataset_id**: Initial state
    - **iterations**: Number of timesteps (1-100)
    - **mask_dataset_id**: Optional mask for constrained propagation
    """
    service = get_ca_service(db)

    try:
        result = await service.ca_run(
            model_id=request.model_id,
            initial_state_dataset_id=request.initial_state_dataset_id,
            iterations=request.iterations,
            mask_dataset_id=request.mask_dataset_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error running CA simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
