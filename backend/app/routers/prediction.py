"""
Prediction and ML Router for TerraCube IDEAS

Provides endpoints for training ML models, making predictions,
and specialized fire spread forecasting.
"""

from fastapi import APIRouter, HTTPException, Body, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.services.prediction import (
    get_prediction_service,
    get_fire_spread_service,
    ModelType,
    PredictionStatus
)
from app.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prediction", tags=["prediction", "ml"])


class TrainingJobRequest(BaseModel):
    dataset_id: str = Field(..., description="Source dataset for training")
    target_attr: str = Field(..., description="Attribute to predict")
    features: List[str] = Field(..., description="Feature attributes")
    model_type: str = Field("linear_regression", description="ML model type")
    test_split: float = Field(0.2, ge=0.0, le=0.5, description="Test data fraction")
    temporal_split: bool = Field(True, description="Split temporally (latest = test)")
    hyperparameters: Optional[Dict[str, Any]] = Field(None, description="Model hyperparameters")


class PredictionJobRequest(BaseModel):
    model_id: str = Field(..., description="Trained model ID")
    dataset_id: str = Field(..., description="Dataset to predict for")
    future_timesteps: int = Field(1, ge=1, le=100, description="Future timesteps to predict")
    prediction_type: str = Field("forecast", description="Type of prediction")


class FireSpreadRequest(BaseModel):
    ignition_dataset_id: str = Field(..., description="Starting fire locations")
    fuel_dataset_id: str = Field(..., description="Fuel load dataset")
    weather_dataset_id: str = Field(..., description="Weather conditions dataset")
    timesteps: int = Field(10, ge=1, le=100, description="Simulation timesteps")
    wind_speed: float = Field(10.0, ge=0.0, le=100.0, description="Wind speed (km/h)")
    wind_direction: float = Field(0.0, ge=0.0, le=360.0, description="Wind direction (degrees)")
    humidity: float = Field(50.0, ge=0.0, le=100.0, description="Relative humidity (%)")


class FireRiskRequest(BaseModel):
    dataset_id: str = Field(..., description="Dataset to analyze")
    weather_scenario: str = Field("normal", description="Weather: normal, dry, extreme")


@router.post("/train")
async def create_training_job(
    request: TrainingJobRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Create a model training job.

    Trains an ML model on historical spatiotemporal data.

    - **dataset_id**: Source dataset for training
    - **target_attr**: Attribute to predict
    - **features**: Feature attributes to use
    - **model_type**: ML algorithm (linear_regression, random_forest, xgboost, lstm, cnn)
    - **test_split**: Fraction for testing (0-0.5)
    - **temporal_split**: Whether to split temporally
    - **hyperparameters**: Optional model hyperparameters

    Returns training job metadata with job_id for status tracking.
    """
    service = get_prediction_service(db)
    user_id = user.get("id")

    try:
        result = await service.create_training_job(
            dataset_id=request.dataset_id,
            target_attr=request.target_attr,
            features=request.features,
            model_type=request.model_type,
            test_split=request.test_split,
            temporal_split=request.temporal_split,
            hyperparameters=request.hyperparameters,
            created_by=user_id
        )

        # Optionally start training immediately
        # await service.train_model(result["job_id"])

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating training job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict")
async def create_prediction_job(
    request: PredictionJobRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Create a prediction job using a trained model.

    - **model_id**: Trained model to use
    - **dataset_id**: Dataset to predict for
    - **future_timesteps**: Number of future timesteps to predict
    - **prediction_type**: Type of prediction (forecast, classify, etc.)

    Returns prediction job metadata.
    """
    service = get_prediction_service(db)
    user_id = user.get("id")

    try:
        result = await service.create_prediction_job(
            model_id=request.model_id,
            dataset_id=request.dataset_id,
            future_timesteps=request.future_timesteps,
            prediction_type=request.prediction_type,
            created_by=user_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating prediction job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fire/spread")
async def predict_fire_spread(
    request: FireSpreadRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Predict wildfire spread using cellular automata + ML.

    - **ignition_dataset_id**: Starting fire locations
    - **fuel_dataset_id**: Fuel load values
    - **weather_dataset_id**: Weather conditions
    - **timesteps**: Simulation steps (1-100)
    - **wind_speed**: Wind speed in km/h (0-100)
    - **wind_direction**: Wind direction in degrees (0-360)
    - **humidity**: Relative humidity percentage (0-100)

    Returns prediction results with burned area and perimeter.
    """
    service = get_fire_spread_service(db)

    try:
        result = await service.predict_fire_spread(
            ignition_dataset_id=request.ignition_dataset_id,
            fuel_dataset_id=request.fuel_dataset_id,
            weather_dataset_id=request.weather_dataset_id,
            timesteps=request.timesteps,
            wind_speed=request.wind_speed,
            wind_direction=request.wind_direction,
            humidity=request.humidity
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error predicting fire spread: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fire/risk")
async def get_fire_risk_map(
    request: FireRiskRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Generate a fire risk map for a dataset.

    - **dataset_id**: Dataset to analyze (fuel, vegetation, etc.)
    - **weather_scenario**: Weather conditions (normal, dry, extreme)

    Returns risk assessment with level breakdowns.
    """
    service = get_fire_spread_service(db)

    try:
        result = await service.get_fire_risk_map(
            dataset_id=request.dataset_id,
            weather_scenario=request.weather_scenario
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating fire risk map: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models(
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    List trained models with optional filters.
    """
    service = get_prediction_service(db)

    try:
        result = await service.list_models(
            created_by=created_by or user.get("id"),
            limit=limit
        )
        return result
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{model_id}")
async def get_model_info(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Get detailed information about a trained model.

    Includes model type, training metrics, hyperparameters, and feature importance.
    """
    service = get_prediction_service(db)

    try:
        result = await service.get_model_info(model_id=model_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/{model_id}/export")
async def export_model(
    model_id: str,
    format: str = Query("pkl", description="Export format: pkl, onnx, json"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Export a trained model for external use.

    Returns download URL that expires after 24 hours.
    """
    service = get_prediction_service(db)

    try:
        result = await service.export_model(
            model_id=model_id,
            export_format=format
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting model: {e}")
        raise HTTPException(status_code=500, detail=str(e))
