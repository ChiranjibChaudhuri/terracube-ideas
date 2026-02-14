"""
Collaborative Annotations Router for TerraCube IDEAS

Enables users to create, list, update, delete, and search annotations
on DGGS cells with shared/private/public visibility.
"""

from fastapi import APIRouter, HTTPException, Body, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.services.annotations import (
    get_annotation_service,
    AnnotationVisibility,
    AnnotationType
)
from app.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


class CreateAnnotationRequest(BaseModel):
    cell_dggid: str = Field(..., description="DGGS cell ID")
    dataset_id: str = Field(..., description="Dataset ID")
    content: str = Field(..., min_length=1, max_length=5000, description="Annotation text content")
    annotation_type: str = Field("note", description="Type: note, warning, question, correction, observation")
    visibility: str = Field("private", description="Visibility: private, shared, public")
    shared_with: Optional[List[str]] = Field(None, description="List of user IDs to share with (for 'shared' visibility)")


class ListAnnotationsRequest(BaseModel):
    dataset_id: str = Field(..., description="Dataset ID")
    bbox: Optional[List[float]] = Field(None, description="Bounding box filter [min_lat, min_lon, max_lat, max_lon]")
    visibility: Optional[str] = Field(None, description="Filter by visibility")
    types: Optional[List[str]] = Field(None, description="Filter by annotation types")
    created_by: Optional[str] = Field(None, description="Filter by creator user ID")
    limit: int = Field(1000, ge=1, le=10000, description="Maximum results to return")


class UpdateAnnotationRequest(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=5000)
    visibility: Optional[str] = Field(None, description="New visibility level")


@router.post("")
async def create_annotation(
    request: CreateAnnotationRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Create a new annotation on a DGGS cell.

    - **cell_dggid**: Target DGGS cell identifier
    - **dataset_id**: Dataset the cell belongs to
    - **content**: Annotation text (1-5000 characters)
    - **annotation_type**: Type of annotation (note, warning, question, correction, observation)
    - **visibility**: Who can see this (private, shared, public)
    - **shared_with**: User IDs to share with (required for 'shared' visibility)
    """
    service = get_annotation_service(db)
    user_id = user.get("id")

    try:
        result = await service.create_annotation(
            cell_dggid=request.cell_dggid,
            dataset_id=request.dataset_id,
            content=request.content,
            annotation_type=request.annotation_type,
            visibility=request.visibility,
            shared_with=request.shared_with,
            created_by=user_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating annotation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dataset/{dataset_id}")
async def list_dataset_annotations(
    dataset_id: str,
    bbox: Optional[str] = Query(None, description="Bounding box as JSON array"),
    visibility: Optional[str] = Query(None, description="Filter by visibility"),
    types: Optional[str] = Query(None, description="Comma-separated annotation types"),
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    limit: int = Query(1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    List annotations for a dataset with optional filters.

    Query parameters:
    - **bbox**: Bounding box filter [min_lat, min_lon, max_lat, max_lon]
    - **visibility**: Filter by visibility level
    - **types**: Comma-separated annotation types
    - **created_by**: Filter by creator user ID
    - **limit**: Maximum results (default 1000)
    """
    import json

    service = get_annotation_service(db)

    # Parse bbox from query string
    parsed_bbox = None
    if bbox:
        try:
            parsed_bbox = json.loads(bbox)
            if len(parsed_bbox) != 4:
                raise ValueError("BBox must have 4 elements")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid bbox format: {e}")

    # Parse types from comma-separated
    parsed_types = None
    if types:
        parsed_types = [t.strip() for t in types.split(",") if t.strip()]

    try:
        result = await service.list_annotations(
            dataset_id=dataset_id,
            bbox=parsed_bbox,
            visibility=visibility,
            types=parsed_types,
            created_by=created_by,
            limit=limit
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing annotations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{annotation_id}")
async def get_annotation(
    annotation_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Get details of a specific annotation.

    Only returns annotations visible to the authenticated user.
    """
    # This would need a get_annotation method in service
    # For now, use list filtered by ID
    service = get_annotation_service(db)
    user_id = user.get("id")

    raise HTTPException(status_code=501, detail="Not yet implemented")


@router.put("/{annotation_id}")
async def update_annotation(
    annotation_id: str,
    request: UpdateAnnotationRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Update an existing annotation.

    Users can only update their own annotations or annotations shared with them.
    - **content**: New annotation text (optional)
    - **visibility**: New visibility level (optional)
    """
    service = get_annotation_service(db)
    user_id = user.get("id")

    try:
        result = await service.update_annotation(
            annotation_id=annotation_id,
            content=request.content,
            visibility=request.visibility,
            user_id=user_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating annotation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{annotation_id}")
async def delete_annotation(
    annotation_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Delete an annotation.

    Only the annotation creator can delete it.
    """
    service = get_annotation_service(db)
    user_id = user.get("id")

    try:
        result = await service.delete_annotation(
            annotation_id=annotation_id,
            user_id=user_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting annotation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_annotations(
    dataset_id: str = Body(..., embed=True),
    query: str = Body(..., min_length=1, max_length=200),
    bbox: Optional[List[float]] = Body(None),
    limit: int = Body(1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Full-text search across annotations in a dataset.

    - **dataset_id**: Dataset to search within
    - **query**: Search query string
    - **bbox**: Optional bounding box filter
    - **limit**: Maximum results (default 1000)
    """
    service = get_annotation_service(db)

    try:
        result = await service.search_annotations(
            dataset_id=dataset_id,
            query=query,
            bbox=bbox,
            limit=limit
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching annotations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
