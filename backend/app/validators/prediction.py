"""
Pydantic validators for prediction and ML operations.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid


class PredictionModelType(str, Enum):
    """Types of prediction models."""
    FIRE_SPREAD = "fire_spread"          # Cellular automata fire spread
    FIRE_RISK = "fire_risk"              # Static fire risk assessment
    LAND_USE = "land_use"                # Land use classification
    CUSTOM = "custom"                    # Custom ML model


class FireSpreadRules(BaseModel):
    """Configuration for fire spread cellular automata."""
    burn_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Fuel threshold for ignition (0-1)"
    )
    spread_probability: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Base spread probability (0-1)"
    )
    wind_direction: Optional[float] = Field(
        default=None,
        ge=0.0,
        lt=360.0,
        description="Wind direction in degrees (0-360)"
    )
    wind_speed: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Wind speed in km/h"
    )
    slope_factor: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Influence of slope on spread (0-1)"
    )


class ModelTrainingRequest(BaseModel):
    """Request model for training a prediction model."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Model name"
    )
    model_type: PredictionModelType = Field(
        ...,
        description="Type of model to train"
    )
    dataset_id: str = Field(
        ...,
        description="Training dataset ID"
    )
    target_attribute: str = Field(
        ...,
        max_length=100,
        description="Target attribute to predict"
    )
    feature_attributes: List[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Attributes to use as features"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Model-specific parameters"
    )
    test_split: float = Field(
        default=0.2,
        ge=0.1,
        le=0.5,
        description="Fraction of data for testing (0.1-0.5)"
    )

    @field_validator('feature_attributes')
    @classmethod
    def validate_features(cls, v: List[str]) -> List[str]:
        """Validate feature list."""
        if not v:
            raise ValueError("feature_attributes cannot be empty")
        # Remove duplicates and limit length
        seen = set()
        unique = []
        for feat in v[:50]:
            feat = feat.strip()[:100]
            if feat and feat not in seen:
                seen.add(feat)
                unique.append(feat)
        return unique


class FireSpreadPredictionRequest(BaseModel):
    """Request model for fire spread prediction."""
    model_id: str = Field(
        ...,
        description="Model ID to use for prediction"
    )
    ignition_cells: List[str] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Initial ignition cell DGGIDs"
    )
    steps: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Number of CA steps to simulate"
    )
    rules: Optional[FireSpreadRules] = Field(
        default=None,
        description="Custom fire spread rules (overrides model defaults)"
    )
    output_interval: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Output every N steps"
    )

    @field_validator('ignition_cells')
    @classmethod
    def validate_ignition_cells(cls, v: List[str]) -> List[str]:
        """Validate ignition cell list."""
        if not v:
            raise ValueError("ignition_cells cannot be empty")
        # Remove duplicates
        return list(set(v))


class FireRiskMapRequest(BaseModel):
    """Request model for generating a fire risk map."""
    dataset_id: str = Field(
        ...,
        description="Dataset containing fuel/vegetation data"
    )
    fuel_attribute: str = Field(
        ...,
        description="Attribute containing fuel data"
    )
    elevation_dataset_id: Optional[str] = Field(
        default=None,
        description="Optional elevation dataset"
    )
    weather_dataset_id: Optional[str] = Field(
        default=None,
        description="Optional weather dataset"
    )
    rules: Optional[FireSpreadRules] = Field(
        default=None,
        description="Custom fire spread rules"
    )
    output_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name for output dataset"
    )


class ModelExportRequest(BaseModel):
    """Request model for exporting a trained model."""
    format: str = Field(
        default="json",
        pattern="^(json|onnx|pickle)$",
        description="Export format"
    )
    include_training_data: bool = Field(
        default=False,
        description="Include training data (not recommended for large models)"
    )
