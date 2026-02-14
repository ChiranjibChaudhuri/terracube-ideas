"""
Common validation utilities and shared validators.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
import uuid
import re


class UUIDPath(str):
    """Pydantic type for validating UUID path parameters."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source):
        from pydantic_core import core_schema
        return core_schema.with_info_schema(
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def validate(cls, value: str) -> uuid.UUID:
        """Validate and parse a UUID string."""
        try:
            return uuid.UUID(value)
        except ValueError:
            raise ValueError(f"Invalid UUID format: {value}")


def sanitize_string(value: str, max_length: int = 255, allow_special: bool = False) -> str:
    """
    Sanitize a user-provided string to prevent injection attacks.

    Args:
        value: The string to sanitize
        max_length: Maximum allowed length
        allow_special: Whether to allow special characters beyond alphanumeric

    Returns:
        Sanitized string safe for database queries
    """
    if not value:
        return ""

    # Remove null bytes and control characters
    sanitized = "".join(c for c in value if ord(c) >= 32 and c not in ('\x00', '\r', '\n'))

    # Trim to max length
    sanitized = sanitized[:max_length]

    # If not allowing special chars, keep only alphanumeric and basic punctuation
    if not allow_special:
        # Keep letters, numbers, spaces, and basic punctuation
        sanitized = "".join(c for c in sanitized if c.isalnum() or c in (' ', '-', '_', '.', ',', '@', '+', '#', '/', ':'))

    return sanitized.strip()


def validate_dggid(dggid: str) -> str:
    """
    Validate and sanitize a DGGS cell ID.

    DGGS IDs are expected to be alphanumeric strings representing
    cells in the discrete global grid system (e.g., "2240000000", "2240011012").
    """
    if not dggid:
        raise ValueError("DGGID cannot be empty")

    # DGGIDs should be alphanumeric (may include leading minus for some DGGS types)
    if not re.match(r'^[a-zA-Z0-9-]+$', dggid):
        raise ValueError(f"Invalid DGGID format: {dggid}")

    if len(dggid) > 256:
        raise ValueError("DGGID too long (max 256 characters)")

    return dggid


def validate_bbox(bbox: Optional[List[float]]) -> Optional[List[float]]:
    """
    Validate a bounding box [min_lat, min_lon, max_lat, max_lon].

    Raises ValueError if the bbox is invalid.
    """
    if bbox is None:
        return None

    if len(bbox) != 4:
        raise ValueError("bbox must have exactly 4 elements: [min_lat, min_lon, max_lat, max_lon]")

    min_lat, min_lon, max_lat, max_lon = bbox

    # Validate latitude (-90 to 90)
    if not (-90 <= min_lat <= 90):
        raise ValueError("min_lat must be between -90 and 90")
    if not (-90 <= max_lat <= 90):
        raise ValueError("max_lat must be between -90 and 90")

    # Validate longitude (-180 to 180)
    if not (-180 <= min_lon <= 180):
        raise ValueError("min_lon must be between -180 and 180")
    if not (-180 <= max_lon <= 180):
        raise ValueError("max_lon must be between -180 and 180")

    # Validate that min < max
    if min_lat >= max_lat:
        raise ValueError("min_lat must be less than max_lat")
    if min_lon >= max_lon:
        raise ValueError("min_lon must be less than max_lon")

    return bbox


class PaginationParams(BaseModel):
    """Common pagination parameters."""
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed)"
    )
    page_size: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Number of items per page (max 1000)"
    )

    @property
    def offset(self) -> int:
        """Calculate SQL offset from page and page_size."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Return the limit for SQL queries."""
        return self.page_size


class SearchParams(BaseModel):
    """Common search/filter parameters."""
    search: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Search term (partial match on name/description)"
    )
    sort_by: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Field to sort by"
    )
    sort_order: Optional[str] = Field(
        default="asc",
        pattern="^(asc|desc)$",
        description="Sort order (asc or desc)"
    )

    @field_validator('search')
    @classmethod
    def sanitize_search_term(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize search term to prevent SQL injection."""
        if v is None:
            return None
        return sanitize_string(v, max_length=100)


class UploadParams(BaseModel):
    """Validation parameters for file uploads."""
    max_file_size: int = Field(
        default=200 * 1024 * 1024,  # 200MB
        ge=1024,
        le=2 * 1024 * 1024 * 1024,  # 2GB
        description="Maximum file size in bytes"
    )
    allowed_extensions: List[str] = Field(
        default_factory=lambda: [".csv", ".json", ".tif", ".tiff", ".geojson", ".shp", ".kml", ".gpkg"],
        description="Allowed file extensions"
    )

    def is_allowed(self, filename: str) -> bool:
        """Check if a filename has an allowed extension."""
        import os
        _, ext = os.path.splitext(filename or "")
        return ext.lower() in self.allowed_extensions
