"""
Pydantic validators for annotation-related operations.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from enum import Enum
import uuid


class AnnotationVisibility(str, Enum):
    """Visibility levels for annotations."""
    PRIVATE = "private"    # Only creator
    SHARED = "shared"      # Creator and specified users
    PUBLIC = "public"      # Everyone


class AnnotationCreateRequest(BaseModel):
    """Request model for creating a new annotation."""
    dggid: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="DGGS cell ID to annotate"
    )
    tid: Optional[int] = Field(
        None,
        ge=0,
        description="Temporal ID (if applicable)"
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Annotation content/text"
    )
    visibility: AnnotationVisibility = Field(
        default=AnnotationVisibility.PRIVATE,
        description="Who can see this annotation"
    )
    metadata: Optional[dict] = Field(
        default=None,
        description="Additional metadata (JSON)"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Tags for categorization"
    )

    @field_validator('content')
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        """Sanitize content to prevent XSS."""
        # Basic HTML/script tag removal
        import re
        # Remove script tags and common XSS patterns
        v = re.sub(r'<script[^>]*>.*?</script>', '', v, flags=re.IGNORECASE | re.DOTALL)
        v = re.sub(r'<iframe[^>]*>.*?</iframe>', '', v, flags=re.IGNORECASE | re.DOTALL)
        v = re.sub(r'on\w+\s*=', '', v, flags=re.IGNORECASE)  # Remove event handlers
        return v[:10000]  # Ensure max length

    @field_validator('tags')
    @classmethod
    def sanitize_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Sanitize tags."""
        if v is None:
            return None
        # Remove empty tags, limit length, limit count
        sanitized = []
        for tag in v[:20]:  # Max 20 tags
            tag = tag.strip()[:50]  # Max 50 chars per tag
            if tag:
                sanitized.append(tag)
        return sanitized or None


class AnnotationUpdateRequest(BaseModel):
    """Request model for updating an annotation."""
    content: Optional[str] = Field(
        None,
        min_length=1,
        max_length=10000,
        description="Updated content"
    )
    visibility: Optional[AnnotationVisibility] = Field(
        None,
        description="Updated visibility"
    )
    metadata: Optional[dict] = Field(
        default=None,
        description="Updated metadata"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Updated tags"
    )

    @field_validator('content')
    @classmethod
    def sanitize_content(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize content if provided."""
        if v is None:
            return None
        import re
        v = re.sub(r'<script[^>]*>.*?</script>', '', v, flags=re.IGNORECASE | re.DOTALL)
        v = re.sub(r'<iframe[^>]*>.*?</iframe>', '', v, flags=re.IGNORECASE | re.DOTALL)
        v = re.sub(r'on\w+\s*=', '', v, flags=re.IGNORECASE)
        return v[:10000]


class AnnotationSearchRequest(BaseModel):
    """Request model for searching annotations."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Full-text search query"
    )
    dggid: Optional[str] = Field(
        None,
        max_length=256,
        description="Filter by DGGS cell ID"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by tags"
    )
    visibility: Optional[AnnotationVisibility] = Field(
        default=None,
        description="Filter by visibility level"
    )
    created_by: Optional[str] = Field(
        None,
        description="Filter by creator user ID"
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum results"
    )
