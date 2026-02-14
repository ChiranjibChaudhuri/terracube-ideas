"""
OGC API Features Router for TerraCube IDEAS

Implements OGC API - Features standard compliance
with separate, modular router for DGGS collections and zones.
Kept separate from core API as requested.
"""

from fastapi import APIRouter, HTTPException, Body, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.services.dggal_utils import get_dggal_service
from app.auth import get_optional_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ogc", tags=["ogc-api-features"])


class ConformanceDeclaration(BaseModel):
    version: str = "1.0.0"
    conformsto: str = "http://www.opengis.net/def/ogc-api-features-1.1"
    type: str = "Feature"


class LandingPage(BaseModel):
    title: str = "TerraCube IDEAS OGC API Features"
    description: str = "DGGS-based spatial data system implementing IDEAS data model"
    links: Dict[str, List[Dict[str, str]]]


class CollectionsList(BaseModel):
    links: List[Dict[str, str]]
    collections: List[Dict[str, Any]]
    number_returned: int
    number_matched: int


class CollectionInfo(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    dggs_name: str
    level: Optional[int] = None
    extent: Optional[Dict[str, Any]] = None
    crs: List[str] = ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"]
    links: Dict[str, str]


class ZonesQuery(BaseModel):
    bbox: List[float] = Field(..., description="Bounding box [min_lon, min_lat, max_lon, max_lat]")
    level: int = Field(..., ge=0, le=20, description="DGGS resolution level")
    limit: int = Field(3000, ge=1, le=50000, description="Maximum zones to return")
    offset: int = Field(0, ge=0, description="Result offset for pagination")


class ZoneFeatures(BaseModel):
    type: str = "FeatureCollection"
    features: List[Dict[str, Any]]
    number_returned: int
    number_matched: Optional[int] = None
    timestamp: str
    links: Dict[str, str]


@router.get("/")
async def ogc_landing_page(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """
    OGC API Features landing page.

    Returns service metadata with links to conformance, collections, and APIs.
    """
    from app.models import Dataset

    # Get base URL from request (in real deployment)
    base_url = "http://localhost:4000"

    # Count collections
    result = await db.execute(select(Dataset.__table__.count()))
    collection_count = result.scalar() or 0

    return {
        "title": "TerraCube IDEAS OGC API Features",
        "description": "DGGS-based spatial data system implementing IDEAS data model on IVEA3H DGGS",
        "links": {
            "self": {"href": f"{base_url}/api/ogc", "type": "application/json", "title": "This document"},
            "conformance": {"href": f"{base_url}/api/ogc/conformance", "type": "application/json", "title": "OGC API Conformance"},
            "collections": {"href": f"{base_url}/api/ogc/collections", "type": "application/json", "title": "Collections"},
            "docs": {"href": f"{base_url}/docs", "type": "text/html", "title": "API Documentation"}
        },
        "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
        "storage_count": collection_count
    }


@router.get("/conformance")
async def ogc_conformance(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """
    OGC API conformance declaration.

    Lists all OGC API specifications this service conforms to.
    """
    base_url = "http://localhost:4000"

    return {
        "conformsTo": [
            "http://www.opengis.net/def/ogc-api-features-1.1",
            "http://www.opengis.net/def/ogc-common-1.1"
        ],
        "title": "TerraCube IDEAS OGC API Features Conformance",
        "links": {
            "self": {"href": f"{base_url}/api/ogc/conformance", "type": "application/json"},
            "service": {"href": f"{base_url}/api/ogc", "type": "application/json"}
        }
    }


@router.get("/collections")
async def list_collections(
    limit: int = Query(100, ge=1, le=1000, description="Maximum collections to return"),
    offset: int = Query(0, ge=0, description="Result offset for pagination"),
    bbox: Optional[str] = Query(None, description="Bounding box filter"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """
    List all DGGS collections (datasets).

    Query parameters:
    - **limit**: Maximum collections to return (default 100)
    - **offset**: Result offset for pagination
    - **bbox**: Optional bounding box filter [min_lon,min_lat,max_lon,max_lat]
    """
    from app.models import Dataset
    import uuid

    base_url = "http://localhost:4000"

    # Build query
    stmt = select(Dataset).where(Dataset.status == "active")
    stmt = stmt.order_by(Dataset.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    datasets = result.scalars().all()

    # Build collections list
    collections = []
    for ds in datasets:
        collections.append({
            "id": str(ds.id),
            "title": ds.name,
            "description": ds.description,
            "dggs_name": ds.dggs_name,
            "level": ds.level,
            "links": {
                "self": {"href": f"{base_url}/api/ogc/collections/{ds.id}", "type": "application/json"},
                "items": {"href": f"{base_url}/api/ogc/collections/{ds.id}/items", "type": "application/geo+json"},
                "zones": {"href": f"{base_url}/api/ogc/collections/{ds.id}/zones", "type": "application/json"}
            }
        })

    # Get total count
    count_stmt = select(Dataset.__table__.count()).where(Dataset.status == "active")
    count_result = await db.execute(count_stmt)
    total_count = count_result.scalar() or 0

    return {
        "links": {
            "self": {"href": f"{base_url}/api/ogc/collections", "type": "application/json"},
            "next": f"{base_url}/api/ogc/collections?offset={offset + limit}&limit={limit}" if len(datasets) == limit else None
        },
        "collections": collections,
        "number_returned": len(datasets),
        "number_matched": total_count
    }


@router.get("/collections/{collection_id}")
async def get_collection(
    collection_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """
    Get detailed metadata for a specific collection (dataset).

    Returns collection info including extent, CRS, and available links.
    """
    from app.models import Dataset, CellObject
    import uuid

    base_url = "http://localhost:4000"

    try:
        ds_uuid = uuid.UUID(collection_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid collection ID format")

    # Get dataset
    stmt = select(Dataset).where(Dataset.id == ds_uuid)
    result = await db.execute(stmt)
    ds = result.first()

    if not ds:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")

    # Get extent from cells
    extent_stmt = select(
        CellObject.dggid
    ).where(
        CellObject.dataset_id == ds_uuid
    ).limit(1)

    # For now, return global extent (in production would compute actual bbox)
    extent = {
        "type": "Global",
        "bbox": [-180, -90, 180, 90]
    }

    return {
        "id": str(ds.id),
        "title": ds.name,
        "description": ds.description,
        "dggs_name": ds.dggs_name,
        "level": ds.level,
        "extent": extent,
        "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
        "links": {
            "self": {"href": f"{base_url}/api/ogc/collections/{collection_id}", "type": "application/json"},
            "items": {"href": f"{base_url}/api/ogc/collections/{collection_id}/items", "type": "application/geo+json"},
            "zones": {"href": f"{base_url}/api/ogc/collections/{collection_id}/zones", "type": "application/json"}
        }
    }


@router.post("/collections/{collection_id}/zones")
async def list_zones(
    collection_id: str,
    request: ZonesQuery = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """
    List DGGS zones for a collection within a bounding box.

    - **collection_id**: Dataset/collection ID
    - **bbox**: Bounding box [min_lon, min_lat, max_lon, max_lat]
    - **level**: DGGS resolution level
    - **limit**: Maximum zones to return
    - **offset**: Result offset
    """
    from app.models import Dataset
    import uuid

    try:
        ds_uuid = uuid.UUID(collection_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid collection ID format")

    # Get dataset
    stmt = select(Dataset).where(Dataset.id == ds_uuid)
    result = await db.execute(stmt)
    ds = result.first()

    if not ds:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")

    # Get DGGAL service
    service = get_dggal_service(ds.dggs_name or "IVEA3H")

    # Validate bbox
    if len(request.bbox) != 4:
        raise HTTPException(status_code=400, detail="bbox must have 4 elements: [min_lon, min_lat, max_lon, max_lat]")

    min_lon, min_lat, max_lon, max_lat = request.bbox

    if min_lon < -180 or min_lon >= 180 or max_lon <= -180 or max_lon > 180:
        raise HTTPException(status_code=400, detail="Longitude must be in range [-180, 180]")
    if min_lat < -90 or min_lat >= 90 or max_lat <= -90 or max_lat > 90:
        raise HTTPException(status_code=400, detail="Latitude must be in range [-90, 90]")

    # List zones for bbox at level
    try:
        zones = service.list_zones_bbox(request.level, [min_lat, min_lon, max_lat, max_lon])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing zones: {str(e)}")

    # Apply limit
    if len(zones) > request.limit:
        zones = zones[:request.limit]

    return {
        "type": "ZoneList",
        "collection_id": collection_id,
        "level": request.level,
        "bbox": request.bbox,
        "zones": zones,
        "number_returned": len(zones)
    }


@router.get("/collections/{collection_id}/items")
async def get_features(
    collection_id: str,
    bbox: Optional[str] = Query(None, description="Bounding box filter"),
    level: Optional[int] = Query(None, description="DGGS resolution level"),
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    zones: Optional[str] = Query(None, description="Comma-separated zone IDs"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """
    Get features (cells) for a collection as GeoJSON.

    Query parameters:
    - **bbox**: Optional bounding box filter
    - **level**: Optional DGGS resolution level
    - **limit**: Maximum features to return
    - **offset**: Result offset
    - **zones**: Comma-separated zone IDs to filter
    """
    from app.models import Dataset, CellObject
    import uuid

    base_url = "http://localhost:4000"

    try:
        ds_uuid = uuid.UUID(collection_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid collection ID format")

    # Get dataset
    stmt = select(Dataset).where(Dataset.id == ds_uuid)
    result = await db.execute(stmt)
    ds = result.first()

    if not ds:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")

    # Get DGGAL service
    service = get_dggal_service(ds.dggs_name or "IVEA3H")

    # Build query
    stmt = select(
        CellObject.dggid,
        CellObject.tid,
        CellObject.attr_key,
        CellObject.value_num,
        CellObject.value_text
    ).where(
        CellObject.dataset_id == ds_uuid
    )

    # Apply zone filter if provided
    if zones:
        zone_list = [z.strip() for z in zones.split(",")]
        stmt = stmt.where(CellObject.dggid.in_(zone_list))

    # Apply level filter if provided
    if level is not None:
        # This would require DGGAL to check zone level
        pass

    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    cells = result.mappings().all()

    # Build GeoJSON features
    features = []
    for cell in cells:
        dggid = cell.get("dggid")

        # Get centroid for point geometry
        try:
            centroid = service.get_centroid(dggid)
            geometry = {
                "type": "Point",
                "coordinates": [centroid["lon"], centroid["lat"]]
            }
        except Exception:
            # Fallback to empty geometry
            geometry = {
                "type": "Point",
                "coordinates": [0, 0]
            }

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "dggid": dggid,
                "tid": cell.get("tid"),
                "attr_key": cell.get("attr_key"),
                "value_num": cell.get("value_num"),
                "value_text": cell.get("value_text")
            },
            "id": dggid
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "number_returned": len(features),
        "number_matched": len(features),
        "timestamp": f"{limit}:{offset}",
        "links": {
            "self": {"href": f"{base_url}/api/ogc/collections/{collection_id}/items", "type": "application/geo+json"},
            "collection": {"href": f"{base_url}/api/ogc/collections/{collection_id}", "type": "application/json"}
        }
    }


@router.get("/collections/{collection_id}/zones/{zone_id}")
async def get_zone_feature(
    collection_id: str,
    zone_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """
    Get a specific zone feature as GeoJSON.

    Returns full zone geometry and all attributes.
    """
    from app.models import Dataset, CellObject
    import uuid

    base_url = "http://localhost:4000"

    try:
        ds_uuid = uuid.UUID(collection_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid collection ID format")

    # Get dataset
    stmt = select(Dataset).where(Dataset.id == ds_uuid)
    result = await db.execute(stmt)
    ds = result.first()

    if not ds:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")

    # Get DGGAL service
    service = get_dggal_service(ds.dggs_name or "IVEA3H")

    # Get all cell data for zone
    stmt = select(
        CellObject.dggid,
        CellObject.tid,
        CellObject.attr_key,
        CellObject.value_num,
        CellObject.value_text,
        CellObject.value_json
    ).where(
        CellObject.dataset_id == ds_uuid,
        CellObject.dggid == zone_id
    )

    result = await db.execute(stmt)
    cells = result.mappings().all()

    if not cells:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")

    # Get full geometry (vertices)
    try:
        vertices = service.get_vertices(zone_id)
        if vertices and len(vertices) >= 3:
            # Build polygon
            coordinates = [[v["lon"], v["lat"]] for v in vertices]
            # Close the ring
            coordinates.append(coordinates[0])
            geometry = {
                "type": "Polygon",
                "coordinates": [coordinates]
            }
        else:
            # Fallback to centroid
            centroid = service.get_centroid(zone_id)
            geometry = {
                "type": "Point",
                "coordinates": [centroid["lon"], centroid["lat"]]
            }
    except Exception:
        # Final fallback to empty point
        geometry = {
            "type": "Point",
            "coordinates": [0, 0]
        }

    # Collect all attributes
    properties = {
        "dggid": zone_id,
        "attributes": {}
    }

    for cell in cells:
        attr_key = cell.get("attr_key")
        properties["attributes"][attr_key] = {
            "tid": cell.get("tid"),
            "value_num": cell.get("value_num"),
            "value_text": cell.get("value_text"),
            "value_json": cell.get("value_json")
        }

    return {
        "type": "Feature",
        "id": zone_id,
        "geometry": geometry,
        "properties": properties,
        "links": {
            "self": {"href": f"{base_url}/api/ogc/collections/{collection_id}/zones/{zone_id}", "type": "application/geo+json"},
            "collection": {"href": f"{base_url}/api/ogc/collections/{collection_id}", "type": "application/json"}
        }
    }


@router.get("/definitions")
async def get_definitions(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """
    Get API definitions and schemas.

    Returns OpenAPI-like definitions for OGC API resources.
    """
    base_url = "http://localhost:4000"

    return {
        "openapi": "3.0.0",
        "info": {
            "title": "TerraCube IDEAS OGC API Features",
            "version": "1.0.0",
            "description": "DGGS-based spatial data system implementing OGC API Features standard"
        },
        "servers": [
            {"url": base_url, "description": "Development server"}
        ],
        "paths": {
            "/api/ogc": {"get": {"summary": "Landing page"}},
            "/api/ogc/conformance": {"get": {"summary": "Conformance declaration"}},
            "/api/ogc/collections": {"get": {"summary": "List collections"}},
            "/api/ogc/collections/{collection_id}": {"get": {"summary": "Get collection"}},
            "/api/ogc/collections/{collection_id}/items": {"get": {"summary": "Get features"}},
            "/api/ogc/collections/{collection_id}/zones": {"post": {"summary": "List zones"}}
        },
        "components": {
            "schemas": {
                "collection": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "title": {"type": "string"},
                        "description": {"type": "string"}
                    }
                },
                "feature": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["Feature"]},
                        "geometry": {"type": "object"},
                        "properties": {"type": "object"}
                    }
                }
            }
        }
    }
