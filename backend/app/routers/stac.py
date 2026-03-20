"""STAC-DGGS API Router: search catalogs, manage collections, ingest scenes."""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import Dataset
from app.models_stac import StacCatalog, StacCollection, StacScene
from app.repositories.dataset_repo import DatasetRepository
from app.services.stac_discovery import StacDiscovery
from app.services.stac_indexer import DGGSCollectionIndexer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stac", tags=["stac"])

# ── Request/Response Models ──────────────────────────────────────

class CatalogOut(BaseModel):
    id: str
    name: str
    api_url: str
    catalog_type: str
    auth_type: Optional[str] = None
    collections: list = Field(default_factory=list)


class SearchRequest(BaseModel):
    collection: str = Field(..., description="STAC collection ID, e.g. 'sentinel-2-l2a'")
    bbox: Optional[List[float]] = Field(None, description="[west, south, east, north]")
    date_start: Optional[str] = Field(None, description="YYYY-MM-DD")
    date_end: Optional[str] = Field(None, description="YYYY-MM-DD")
    cloud_cover_lt: Optional[float] = Field(None, ge=0, le=100)
    max_items: int = Field(50, ge=1, le=500)


class CreateCollectionRequest(BaseModel):
    catalog_id: str
    stac_collection: str
    name: str
    bbox: Optional[List[float]] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    cloud_cover_lt: Optional[float] = None
    max_items: int = 50


class IngestRequest(BaseModel):
    scene_ids: List[str] = Field(..., min_length=1)
    bands: List[str] = Field(..., min_length=1)
    target_level: int = Field(9, ge=1, le=15)
    dataset_name: Optional[str] = None
    dataset_id: Optional[str] = None


def _parse_uuid(value: str, detail: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=detail) from exc


def _can_access_collection(collection: StacCollection, user: dict) -> bool:
    if user.get("role") == "admin":
        return True
    if collection.created_by is None:
        return False
    return str(collection.created_by) == user["id"]


def _can_write_dataset(dataset: Dataset, user: dict) -> bool:
    if user.get("role") == "admin":
        return True
    if dataset.created_by is None:
        return False
    return str(dataset.created_by) == user["id"]


async def _get_collection_or_404(
    db: AsyncSession,
    collection_id: str,
    user: dict,
) -> StacCollection:
    collection_uuid = _parse_uuid(collection_id, "Invalid collection ID")
    result = await db.execute(
        select(StacCollection).where(StacCollection.id == collection_uuid)
    )
    collection = result.scalars().first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not _can_access_collection(collection, user):
        raise HTTPException(status_code=403, detail="Not authorized to access this collection")
    return collection


async def _resolve_ingest_dataset(
    db: AsyncSession,
    request: IngestRequest,
    collection: StacCollection,
    user: dict,
) -> Dataset:
    metadata_patch = {
        "source_type": "stac",
        "stac_collection_id": str(collection.id),
        "bands": request.bands,
        "target_level": request.target_level,
    }

    if request.dataset_id:
        dataset_uuid = _parse_uuid(request.dataset_id, "Invalid dataset ID")
        result = await db.execute(
            select(Dataset).where(Dataset.id == dataset_uuid)
        )
        dataset = result.scalars().first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        if not _can_write_dataset(dataset, user):
            raise HTTPException(status_code=403, detail="Not authorized to update this dataset")
        if dataset.dggs_name and dataset.dggs_name != "IVEA3H":
            raise HTTPException(
                status_code=400,
                detail="STAC ingestion currently supports only IVEA3H datasets",
            )

        dataset.status = "processing"
        dataset.metadata_ = {**(dataset.metadata_ or {}), **metadata_patch}
        await db.commit()
        return dataset

    dataset_repo = DatasetRepository(db)
    dataset_name = request.dataset_name or f"{collection.name} - Ingestion"
    description = f"STAC ingestion target for {collection.name}"
    return await dataset_repo.create(
        name=dataset_name,
        description=description,
        dggs_name="IVEA3H",
        status="processing",
        metadata_=metadata_patch,
        created_by=uuid.UUID(user["id"]),
    )


# ── Catalog Endpoints ────────────────────────────────────────────

@router.get("/catalogs")
async def list_catalogs(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List all configured STAC catalogs."""
    result = await db.execute(select(StacCatalog).order_by(StacCatalog.name))
    catalogs = result.scalars().all()
    return [
        CatalogOut(
            id=str(c.id),
            name=c.name,
            api_url=c.api_url,
            catalog_type=c.catalog_type,
            auth_type=c.auth_type,
            collections=c.collections or [],
        )
        for c in catalogs
    ]


@router.post("/catalogs/{catalog_id}/search")
async def search_catalog(
    catalog_id: str,
    request: SearchRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Search a STAC catalog for scenes matching criteria.

    Returns scene metadata without creating a persistent collection.
    """
    # Fetch catalog
    catalog_uuid = _parse_uuid(catalog_id, "Invalid catalog ID")
    result = await db.execute(
        select(StacCatalog).where(StacCatalog.id == catalog_uuid)
    )
    catalog = result.scalars().first()
    if not catalog:
        raise HTTPException(status_code=404, detail="STAC catalog not found")

    discovery = StacDiscovery()

    bbox = tuple(request.bbox) if request.bbox and len(request.bbox) == 4 else None
    date_range = None
    if request.date_start and request.date_end:
        date_range = (request.date_start, request.date_end)

    try:
        scenes = discovery.search(
            api_url=catalog.api_url,
            collection=request.collection,
            auth_type=catalog.auth_type,
            bbox=bbox,
            date_range=date_range,
            cloud_cover_lt=request.cloud_cover_lt,
            max_items=request.max_items,
        )
    except Exception as e:
        logger.error("STAC search failed: %s", str(e))
        raise HTTPException(status_code=502, detail=f"STAC API error: {str(e)}")

    # Include available bands for this collection
    available_bands = discovery.get_available_bands(request.collection, scenes=scenes)

    return {
        "scenes": scenes,
        "count": len(scenes),
        "available_bands": available_bands,
        "catalog": catalog.name,
        "collection": request.collection,
    }


@router.get("/catalogs/{catalog_id}/bands/{collection}")
async def get_collection_bands(
    catalog_id: str,
    collection: str,
    user: dict = Depends(get_current_user),
):
    """Get available band names for a STAC collection."""
    discovery = StacDiscovery()
    bands = discovery.get_available_bands(collection)
    return {"collection": collection, "bands": bands}


# ── Collection Endpoints ─────────────────────────────────────────

@router.post("/collections")
async def create_collection(
    request: CreateCollectionRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Create a DGGS-indexed collection from a STAC search.

    Searches the STAC catalog, computes DGGS cell coverage for each scene,
    and stores the indexed collection for later ingestion.
    """
    indexer = DGGSCollectionIndexer(db)

    bbox = tuple(request.bbox) if request.bbox and len(request.bbox) == 4 else None
    date_range = None
    if request.date_start and request.date_end:
        date_range = (request.date_start, request.date_end)

    try:
        result = await indexer.build_collection(
            catalog_id=request.catalog_id,
            stac_collection=request.stac_collection,
            name=request.name,
            user_id=user["id"],
            bbox=bbox,
            date_range=date_range,
            cloud_cover_lt=request.cloud_cover_lt,
            max_items=request.max_items,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Collection creation failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))

    return result


@router.get("/collections")
async def list_collections(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List STAC collections created by the current user."""
    result = await db.execute(
        select(StacCollection)
        .where(StacCollection.created_by == uuid.UUID(user["id"]))
        .order_by(StacCollection.created_at.desc())
    )
    collections = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "stac_collection": c.stac_collection,
            "bbox": c.bbox,
            "date_start": str(c.date_start) if c.date_start else None,
            "date_end": str(c.date_end) if c.date_end else None,
            "scene_count": c.scene_count,
            "status": c.status,
            "error": c.error,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in collections
    ]


@router.get("/collections/{collection_id}")
async def get_collection(
    collection_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get a STAC collection with its scenes."""
    collection = await _get_collection_or_404(db, collection_id, user)
    collection_uuid = collection.id

    # Fetch scenes
    scenes_result = await db.execute(
        select(StacScene)
        .where(StacScene.collection_id == collection_uuid)
        .order_by(StacScene.datetime.desc().nullslast())
    )
    scenes = scenes_result.scalars().all()
    discovery = StacDiscovery()
    available_bands = discovery.get_available_bands(
        collection.stac_collection,
        scenes=[{"bands": s.bands or {}} for s in scenes],
    )

    return {
        "id": str(collection.id),
        "name": collection.name,
        "stac_collection": collection.stac_collection,
        "bbox": collection.bbox,
        "date_start": str(collection.date_start) if collection.date_start else None,
        "date_end": str(collection.date_end) if collection.date_end else None,
        "scene_count": collection.scene_count,
        "status": collection.status,
        "error": collection.error,
        "created_at": collection.created_at.isoformat() if collection.created_at else None,
        "available_bands": available_bands,
        "scenes": [
            {
                "id": str(s.id),
                "stac_item_id": s.stac_item_id,
                "datetime": s.datetime.isoformat() if s.datetime else None,
                "cloud_cover": s.cloud_cover,
                "bbox": s.bbox,
                "bands": list(s.bands.keys()) if s.bands else [],
                "thumbnail_url": s.thumbnail_url,
                "dggs_cell_count": len(s.dggs_coverage) if s.dggs_coverage else 0,
                "ingested": s.ingested,
                "dataset_id": str(s.dataset_id) if s.dataset_id else None,
            }
            for s in scenes
        ],
    }


@router.delete("/collections/{collection_id}")
async def delete_collection(
    collection_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Delete a STAC collection and all its scenes."""
    collection = await _get_collection_or_404(db, collection_id, user)

    await db.execute(
        delete(StacCollection).where(StacCollection.id == collection.id)
    )
    await db.commit()
    return {"deleted": True}


# ── Ingestion Endpoints ──────────────────────────────────────────

@router.post("/collections/{collection_id}/ingest")
async def ingest_scenes(
    collection_id: str,
    request: IngestRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Ingest selected scenes from a STAC collection into IDEAS cell objects.

    Launches a background Celery task that:
    1. Opens each scene's COG bands via HTTP range requests
    2. Samples raster values at DGGS cell centroids
    3. Creates IDEAS cell objects with tid = scene epoch seconds
    """
    collection = await _get_collection_or_404(db, collection_id, user)
    scene_uuids = [_parse_uuid(scene_id, "Invalid scene ID") for scene_id in request.scene_ids]

    selected_scenes_result = await db.execute(
        select(StacScene).where(
            StacScene.collection_id == collection.id,
            StacScene.id.in_(scene_uuids),
        )
    )
    selected_scenes = selected_scenes_result.scalars().all()
    if len(selected_scenes) != len(request.scene_ids):
        raise HTTPException(status_code=400, detail="Some scene IDs not found in this collection")

    discovery = StacDiscovery()
    available_bands = discovery.get_available_bands(
        collection.stac_collection,
        scenes=[{"bands": s.bands or {}} for s in selected_scenes],
    )
    missing_bands = sorted(set(request.bands) - set(available_bands))
    if missing_bands:
        raise HTTPException(
            status_code=400,
            detail=f"Requested bands are not available for the selected scenes: {', '.join(missing_bands)}",
        )

    dataset = await _resolve_ingest_dataset(db, request, collection, user)
    dataset_name = dataset.name

    # Launch Celery task
    from app.services.stac_ingest import ingest_stac_scenes

    try:
        task = ingest_stac_scenes.delay(
            collection_id=str(collection.id),
            scene_ids=request.scene_ids,
            dataset_name=dataset_name,
            dataset_id=str(dataset.id),
            bands=request.bands,
            target_level=request.target_level,
            user_id=user["id"],
            dggs_name=dataset.dggs_name or "IVEA3H",
        )
    except Exception as exc:
        dataset.status = "failed"
        dataset.metadata_ = {
            **(dataset.metadata_ or {}),
            "last_error": f"Failed to launch STAC ingestion task: {exc}",
        }
        await db.commit()
        raise HTTPException(status_code=502, detail="Failed to launch ingestion worker") from exc

    return {
        "task_id": task.id,
        "status": "processing",
        "collection_id": str(collection.id),
        "dataset_id": str(dataset.id),
        "scene_count": len(request.scene_ids),
        "bands": request.bands,
        "target_level": request.target_level,
        "dataset_name": dataset_name,
    }


@router.get("/collections/{collection_id}/scenes/{scene_id}/coverage")
async def get_scene_coverage(
    collection_id: str,
    scene_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get the DGGS cell coverage for a specific scene."""
    collection = await _get_collection_or_404(db, collection_id, user)
    scene_uuid = _parse_uuid(scene_id, "Invalid scene ID")
    result = await db.execute(
        select(StacScene).where(
            StacScene.id == scene_uuid,
            StacScene.collection_id == collection.id,
        )
    )
    scene = result.scalars().first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    return {
        "scene_id": str(scene.id),
        "stac_item_id": scene.stac_item_id,
        "dggs_coverage": scene.dggs_coverage or [],
        "cell_count": len(scene.dggs_coverage) if scene.dggs_coverage else 0,
        "coverage_level": 5,
    }
