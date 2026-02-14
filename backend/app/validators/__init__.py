"""
Validators package for TerraCube IDEAS.

Provides Pydantic models for validating all API request inputs.
"""

from .common import (
    UUIDPath,
    PaginationParams,
    SearchParams,
    UploadParams,
    sanitize_string,
    validate_dggid,
    validate_bbox,
)
from .datasets import (
    DGGSName,
    DatasetCreateRequest,
    DatasetUpdateRequest,
    CellLookupRequest,
    CellListRequest,
    DatasetExportRequest,
    SpatialOperationRequest,
    ZonalStatsRequest,
)
from .annotations import (
    AnnotationVisibility,
    AnnotationCreateRequest,
    AnnotationUpdateRequest,
    AnnotationSearchRequest,
)
from .prediction import (
    PredictionModelType,
    FireSpreadRules,
    ModelTrainingRequest,
    FireSpreadPredictionRequest,
    FireRiskMapRequest,
    ModelExportRequest,
)
from .temporal import (
    TemporalLevel,
    TemporalOperation,
    CARuleType,
    TemporalSnapshotRequest,
    TemporalRangeRequest,
    TemporalAggregateRequest,
    CAInitializeRequest,
    CAStepRequest,
    CARunRequest,
)

__all__ = [
    # Common
    "UUIDPath",
    "PaginationParams",
    "SearchParams",
    "UploadParams",
    "sanitize_string",
    "validate_dggid",
    "validate_bbox",
    # Datasets
    "DGGSName",
    "DatasetCreateRequest",
    "DatasetUpdateRequest",
    "CellLookupRequest",
    "CellListRequest",
    "DatasetExportRequest",
    "SpatialOperationRequest",
    "ZonalStatsRequest",
    # Annotations
    "AnnotationVisibility",
    "AnnotationCreateRequest",
    "AnnotationUpdateRequest",
    "AnnotationSearchRequest",
    # Prediction
    "PredictionModelType",
    "FireSpreadRules",
    "ModelTrainingRequest",
    "FireSpreadPredictionRequest",
    "FireRiskMapRequest",
    "ModelExportRequest",
    # Temporal
    "TemporalLevel",
    "TemporalOperation",
    "CARuleType",
    "TemporalSnapshotRequest",
    "TemporalRangeRequest",
    "TemporalAggregateRequest",
    "CAInitializeRequest",
    "CAStepRequest",
    "CARunRequest",
]
