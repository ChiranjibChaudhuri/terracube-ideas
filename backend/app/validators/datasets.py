"""
Pydantic validators for dataset-related operations.
Provides strict input validation and user-friendly error messages.
"""
from pydantic import BaseModel, Field, field_validator, validator
from typing import Optional, List
from enum import Enum
import uuid
import re


class DGGSName(str, Enum):
    """Supported DGGS names"""
    IVEA3H = "IVEA3H"
    ISEA3H = "ISEA3H"
    IVEA7H = "IVEA7H"
    ISEA7H = "ISEA7H"


class DatasetCreateRequest(BaseModel):
    """Request model for creating a new dataset."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Dataset name"
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Dataset description"
    )
    dggs_name: DGGSName = Field(
        default=DGGSName.IVEA3H,
        description="DGGS reference system name"
    )
    level: Optional[int] = Field(
        None,
        ge=0,
        le=30,
        description="DGGS refinement level (0-30)"
    )

    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()


class DatasetUpdateRequest(BaseModel):
    """Request model for updating a dataset."""
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Dataset name"
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Dataset description"
    )
    status: Optional[str] = Field(
        None,
        pattern="^(active|archived|processing|failed)$",
        description="Dataset status"
    )

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ["active", "archived", "processing", "failed"]:
            raise ValueError("Status must be one of: active, archived, processing, failed")
        return v


class CellLookupRequest(BaseModel):
    """Request model for cell lookup operations."""
    dggids: List[str] = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="List of DGGS cell identifiers"
    )
    key: Optional[str] = Field(
        None,
        max_length=100,
        description="Attribute key to filter by"
    )
    tid: Optional[int] = Field(
        None,
        ge=0,
        description="Temporal ID to filter by"
    )

    @field_validator('dggids')
    @classmethod
    def validate_dggids(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("dggids cannot be empty")
        # Remove duplicates
        seen = set()
        unique = []
        for dggid in v:
            if dggid not in seen:
                seen.add(dggid)
                unique.append(dggid)
        return unique


class CellListRequest(BaseModel):
    """Request model for listing cells with filters."""
    key: Optional[str] = Field(
        None,
        max_length=100,
        description="Attribute key to filter by"
    )
    dggid_prefix: Optional[str] = Field(
        None,
        max_length=50,
        description="Filter by dggid prefix"
    )
    tid: Optional[int] = Field(
        None,
        ge=0,
        description="Temporal ID to filter by"
    )
    limit: int = Field(
        default=500,
        ge=1,
        le=10000,
        description="Maximum number of results"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip"
    )


class DatasetExportRequest(BaseModel):
    """Request model for dataset export."""
    format: str = Field(
        ...,
        pattern="^(csv|geojson)$",
        description="Export format (csv or geojson)"
    )
    bbox: Optional[List[float]] = Field(
        None,
        description="Bounding box filter [min_lat, min_lon, max_lat, max_lon]"
    )

    @field_validator('bbox')
    @classmethod
    def validate_bbox(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        if v is not None:
            if len(v) != 4:
                raise ValueError("bbox must have exactly 4 elements: [min_lat, min_lon, max_lat, max_lon]")
            if not all(-90 <= coord <= 90 for coord in [v[0], v[2]]):
                raise ValueError("Latitude must be between -90 and 90")
            if not all(-180 <= coord <= 180 for coord in [v[1], v[3]]):
                raise ValueError("Longitude must be between -180 and 180")
        return v


class SpatialOperationRequest(BaseModel):
    """Request model for spatial operations."""
    type: str = Field(
        ...,
        pattern="^(intersection|union|difference|buffer|aggregate|simplify|clip|kRing|onalStats)$",
        description="Operation type"
    )
    dataset_a_id: str = Field(
        ...,
        description="First dataset ID"
    )
    dataset_b_id: Optional[str] = Field(
        None,
        description="Second dataset ID (for binary operations)"
    )
    key_a: str = Field(
        default="value",
        max_length=100,
        description="Attribute key for dataset A"
    )
    key_b: str = Field(
        default="value",
        max_length=100,
        description="Attribute key for dataset B"
    )
    limit: Optional[int] = Field(
        None,
        ge=1,
        le=100,
        description="Operation parameter (buffer rings, aggregation levels, etc.)"
    )

    @field_validator('dataset_a_id', 'dataset_b_id')
    @classmethod
    def validate_uuids(cls, v_a, v_b):
        """Validate UUID format."""
        try:
            uuid.UUID(v_a)
        except ValueError:
            raise ValueError("dataset_a_id must be a valid UUID")
        if v_b:
            try:
                uuid.UUID(v_b)
            except ValueError:
                raise ValueError("dataset_b_id must be a valid UUID")
        return v_a, v_b


class ZonalStatsRequest(BaseModel):
    """Request model for zonal statistics."""
    zone_dataset_id: str = Field(
        ...,
        description="Zone dataset ID"
    )
    value_dataset_id: str = Field(
        ...,
        description="Value dataset ID"
    )
    operation: str = Field(
        default="MEAN",
        pattern="^(MEAN|MAX|MIN|COUNT|SUM)$",
        description="Statistical operation"
    )

    @field_validator('zone_dataset_id', 'value_dataset_id')
    @classmethod
    def validate_uuids(cls, zone_id, value_id):
        """Validate UUID format."""
        try:
            uuid.UUID(zone_id)
        except ValueError:
            raise ValueError("zone_dataset_id must be a valid UUID")
        try:
            uuid.UUID(value_id)
        except ValueError:
            raise ValueError("value_dataset_id must be a valid UUID")
        return zone_id, value_id
