"""STAC Collection Indexer: build DGGS-indexed collections from STAC search results."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dggal_utils import get_dggal_service
from app.models_stac import StacCatalog, StacCollection, StacScene
from app.services.stac_discovery import StacDiscovery

logger = logging.getLogger(__name__)

# Coarse level for DGGS coverage indexing (cells ~100-200km across)
COVERAGE_LEVEL = 5


class DGGSCollectionIndexer:
    """Index STAC scenes by DGGS cell coverage."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.discovery = StacDiscovery()
        self.dggal = get_dggal_service("IVEA3H")

    async def build_collection(
        self,
        catalog_id: str,
        stac_collection: str,
        name: str,
        user_id: str,
        auth_type: Optional[str] = None,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        date_range: Optional[Tuple[str, str]] = None,
        cloud_cover_lt: Optional[float] = None,
        max_items: int = 50,
    ) -> Dict[str, Any]:
        """Build a DGGS-indexed collection from a STAC search.

        1. Search STAC API for scenes matching criteria
        2. For each scene: compute DGGS cell coverage at coarse level
        3. Store scene records in stac_scenes table
        4. Return collection metadata

        Args:
            catalog_id: UUID of the stac_catalogs record
            stac_collection: STAC collection ID (e.g. "sentinel-2-l2a")
            name: User-friendly name for this collection
            user_id: UUID of the requesting user
            bbox: (west, south, east, north) bounding box
            date_range: ("YYYY-MM-DD", "YYYY-MM-DD")
            cloud_cover_lt: Max cloud cover percentage filter
            max_items: Maximum scenes to discover

        Returns:
            Dict with collection id, name, scene_count, status
        """
        # Fetch catalog API URL
        catalog = await self.db.execute(
            select(StacCatalog).where(StacCatalog.id == uuid.UUID(catalog_id))
        )
        catalog_row = catalog.scalars().first()
        if not catalog_row:
            raise ValueError(f"STAC catalog not found: {catalog_id}")

        # Create collection record (status: indexing)
        collection_id = uuid.uuid4()
        collection = StacCollection(
            id=collection_id,
            name=name,
            catalog_id=catalog_row.id,
            stac_collection=stac_collection,
            bbox=list(bbox) if bbox else None,
            date_start=datetime.strptime(date_range[0], "%Y-%m-%d").date() if date_range else None,
            date_end=datetime.strptime(date_range[1], "%Y-%m-%d").date() if date_range else None,
            query_params={
                "cloud_cover_lt": cloud_cover_lt,
                "max_items": max_items,
            },
            status="indexing",
            created_by=uuid.UUID(user_id),
        )
        self.db.add(collection)
        await self.db.commit()

        try:
            # Search STAC API
            scenes = self.discovery.search(
                api_url=catalog_row.api_url,
                collection=stac_collection,
                auth_type=auth_type or catalog_row.auth_type,
                bbox=bbox,
                date_range=date_range,
                cloud_cover_lt=cloud_cover_lt,
                max_items=max_items,
            )

            if not scenes:
                await self._update_collection_status(
                    collection_id, "failed", "No scenes found matching criteria"
                )
                return {
                    "id": str(collection_id),
                    "name": name,
                    "scene_count": 0,
                    "status": "failed",
                    "error": "No scenes found matching criteria",
                }

            # Index each scene with DGGS coverage
            scene_records = []
            for scene_data in scenes:
                scene = self._build_scene_record(collection_id, scene_data)
                scene_records.append(scene)

            # Bulk insert scenes
            self.db.add_all(scene_records)
            await self.db.flush()

            # Update collection status
            await self.db.execute(
                update(StacCollection)
                .where(StacCollection.id == collection_id)
                .values(
                    scene_count=len(scene_records),
                    status="ready",
                    error=None,
                )
            )
            await self.db.commit()

            logger.info(
                "Collection %s ready: %d scenes indexed",
                str(collection_id), len(scene_records),
            )

            return {
                "id": str(collection_id),
                "name": name,
                "scene_count": len(scene_records),
                "status": "ready",
            }

        except Exception as e:
            logger.error("Collection indexing failed: %s", str(e))
            await self._update_collection_status(collection_id, "failed", str(e))
            raise

    def _build_scene_record(
        self, collection_id: uuid.UUID, scene_data: Dict[str, Any]
    ) -> StacScene:
        """Create a StacScene ORM record from STAC item metadata."""
        # Compute DGGS coverage from scene bbox
        scene_bbox = scene_data.get("bbox")
        dggs_coverage = []
        if scene_bbox and len(scene_bbox) >= 4:
            dggs_coverage = self._compute_dggs_coverage(scene_bbox)

        # Parse datetime
        dt_value = None
        if scene_data.get("datetime"):
            try:
                dt_str = scene_data["datetime"]
                if dt_str.endswith("Z"):
                    dt_str = dt_str[:-1] + "+00:00"
                dt_value = datetime.fromisoformat(dt_str)
            except (ValueError, TypeError):
                pass

        return StacScene(
            id=uuid.uuid4(),
            collection_id=collection_id,
            stac_item_id=scene_data["stac_item_id"],
            datetime=dt_value,
            cloud_cover=scene_data.get("cloud_cover"),
            bbox=scene_bbox,
            bands=scene_data.get("bands", {}),
            properties=scene_data.get("properties", {}),
            thumbnail_url=scene_data.get("thumbnail_url"),
            dggs_coverage=dggs_coverage,
            ingested=False,
            dataset_id=None,
        )

    def _compute_dggs_coverage(self, bbox: List[float]) -> List[str]:
        """Map a scene bounding box to DGGS cells at the coverage index level.

        Args:
            bbox: [west, south, east, north] in WGS84

        Returns:
            List of DGGS cell IDs that overlap the bbox
        """
        # Convert from [west, south, east, north] to dggal [S, W, N, E]
        dgg_bbox = [bbox[1], bbox[0], bbox[3], bbox[2]]
        try:
            zones = self.dggal.list_zones_bbox(COVERAGE_LEVEL, dgg_bbox)
            # Limit to prevent huge arrays for global datasets
            if len(zones) > 500:
                logger.warning(
                    "Scene covers %d DGGS cells at level %d, truncating to 500",
                    len(zones), COVERAGE_LEVEL,
                )
                zones = zones[:500]
            return zones
        except Exception as e:
            logger.warning("DGGS coverage computation failed: %s", str(e))
            return []

    async def _update_collection_status(
        self, collection_id: uuid.UUID, status: str, error: Optional[str] = None
    ):
        """Update the status and error of a STAC collection."""
        try:
            await self.db.execute(
                update(StacCollection)
                .where(StacCollection.id == collection_id)
                .values(status=status, error=error)
            )
            await self.db.commit()
        except Exception as e:
            logger.error("Failed to update collection status: %s", str(e))
