"""STAC DGGS Ingestion: Celery tasks for COG-to-DGGS cell sampling.

Reads Cloud-Optimized GeoTIFF tiles via HTTP range requests (no full download),
samples raster values at DGGS cell centroids, and inserts IDEAS cell objects.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import timezone
from math import isfinite
from typing import Dict, List, Optional, Tuple

import rasterio
from rasterio.warp import transform as transform_coords

from app.celery_app import celery_app
from app.db import get_db_pool
from app.dggal_utils import get_dggal_service

logger = logging.getLogger(__name__)

# Maximum cells per scene per band to prevent runaway ingestion
MAX_CELLS_PER_LEVEL = 100_000


@celery_app.task(name="stac_ingest_scenes")
def ingest_stac_scenes(
    collection_id: str,
    scene_ids: List[str],
    dataset_name: str,
    dataset_id: Optional[str],
    bands: List[str],
    target_level: int = 9,
    user_id: Optional[str] = None,
    dggs_name: str = "IVEA3H",
):
    """Celery task: ingest selected STAC scenes into IDEAS cell objects.

    Args:
        collection_id: UUID of the stac_collections record
        scene_ids: List of stac_scenes UUIDs to ingest
        dataset_name: Name for the resulting dataset
        dataset_id: Existing dataset UUID (or None to create new)
        bands: List of band names to ingest (e.g. ["B04", "B08"])
        target_level: DGGS resolution level for sampling
        user_id: UUID of the requesting user
        dggs_name: DGGS system name (default IVEA3H)
    """
    asyncio.run(
        _ingest_scenes_async(
            collection_id, scene_ids, dataset_name, dataset_id,
            bands, target_level, user_id, dggs_name,
        )
    )


async def _ingest_scenes_async(
    collection_id: str,
    scene_ids: List[str],
    dataset_name: str,
    dataset_id: Optional[str],
    bands: List[str],
    target_level: int,
    user_id: Optional[str],
    dggs_name: str,
):
    """Async implementation of STAC scene ingestion."""
    pool = await get_db_pool()
    dggal = get_dggal_service(dggs_name)
    ds_id: Optional[uuid.UUID] = None

    async with pool.acquire() as conn:
        try:
            # Create or fetch target dataset
            ds_id = await _ensure_dataset(
                conn, dataset_id, dataset_name, user_id, dggs_name
            )
            ds_id_str = str(ds_id)

            # Fetch scene metadata
            scenes = await conn.fetch(
                "SELECT id, stac_item_id, datetime, bbox, bands "
                "FROM stac_scenes WHERE collection_id = $1 AND id = ANY($2::uuid[])",
                uuid.UUID(collection_id),
                [uuid.UUID(sid) for sid in scene_ids],
            )

            if not scenes:
                logger.warning("No scenes found for collection %s", collection_id)
                await _set_dataset_state(
                    conn,
                    ds_id,
                    "failed",
                    {
                        "source_type": "stac",
                        "stac_collection_id": collection_id,
                        "bands": bands,
                        "target_level": target_level,
                        "last_error": "No scenes found for the requested collection",
                    },
                )
                return

            logger.info(
                "Ingesting %d scenes into dataset %s at level %d",
                len(scenes), ds_id_str, target_level,
            )

            total_cells = 0
            ingested_scene_count = 0

            for scene_row in scenes:
                scene_id = scene_row["id"]
                stac_item_id = scene_row["stac_item_id"]
                scene_dt = scene_row["datetime"]
                scene_bbox = scene_row["bbox"]
                scene_bands = scene_row["bands"] or {}

                # Compute tid from scene datetime (Unix epoch seconds)
                tid = 0
                if scene_dt:
                    if scene_dt.tzinfo is None:
                        scene_dt = scene_dt.replace(tzinfo=timezone.utc)
                    tid = int(scene_dt.timestamp())

                logger.info("Processing scene %s (tid=%d)", stac_item_id, tid)

                # Compute DGGS cells within scene bbox
                if not scene_bbox or len(scene_bbox) < 4:
                    logger.warning("Scene %s has no bbox, skipping", stac_item_id)
                    continue

                # [west, south, east, north] → dggal [S, W, N, E]
                dgg_bbox = [scene_bbox[1], scene_bbox[0], scene_bbox[3], scene_bbox[2]]
                zones = dggal.list_zones_bbox(target_level, dgg_bbox)

                if not zones:
                    logger.warning("No DGGS zones for scene %s at level %d", stac_item_id, target_level)
                    continue

                if len(zones) > MAX_CELLS_PER_LEVEL:
                    logger.warning(
                        "Scene %s has %d zones at level %d, capping at %d",
                        stac_item_id, len(zones), target_level, MAX_CELLS_PER_LEVEL,
                    )
                    zones = zones[:MAX_CELLS_PER_LEVEL]

                # Pre-compute centroids for all zones
                centroids = {}
                for zone_id in zones:
                    c = dggal.get_centroid(zone_id)
                    centroids[zone_id] = (c["lon"], c["lat"])

                scene_ingested = False

                # Ingest each requested band
                for band_name in bands:
                    if band_name not in scene_bands:
                        logger.warning("Band %s not in scene %s, skipping", band_name, stac_item_id)
                        continue

                    band_info = scene_bands[band_name]
                    cog_url = band_info.get("href", "")
                    if not cog_url:
                        continue

                    cells = _sample_cog_at_centroids(
                        cog_url, centroids, band_name, tid,
                    )

                    if cells:
                        await _insert_cells(conn, ds_id_str, cells)
                        total_cells += len(cells)
                        scene_ingested = True
                        logger.info(
                            "Band %s: sampled %d cells from scene %s",
                            band_name, len(cells), stac_item_id,
                        )

                if scene_ingested:
                    ingested_scene_count += 1
                    await conn.execute(
                        "UPDATE stac_scenes SET ingested = TRUE, dataset_id = $1 WHERE id = $2",
                        ds_id, scene_id,
                    )

            final_status = "active" if total_cells > 0 else "failed"
            metadata_patch = {
                "source_type": "stac",
                "stac_collection_id": collection_id,
                "bands": bands,
                "target_level": target_level,
                "total_cells": total_cells,
                "requested_scene_count": len(scenes),
                "ingested_scene_count": ingested_scene_count,
            }
            if total_cells == 0:
                metadata_patch["last_error"] = (
                    "No STAC cells were ingested for the selected scenes and bands"
                )

            await _set_dataset_state(conn, ds_id, final_status, metadata_patch)

            logger.info(
                "STAC ingestion complete: %d total cells into dataset %s",
                total_cells,
                ds_id_str,
            )
        except Exception as exc:
            logger.exception("STAC ingestion failed for collection %s", collection_id)
            if ds_id is not None:
                await _set_dataset_state(
                    conn,
                    ds_id,
                    "failed",
                    {
                        "source_type": "stac",
                        "stac_collection_id": collection_id,
                        "bands": bands,
                        "target_level": target_level,
                        "last_error": str(exc),
                    },
                )
            raise


def _sample_cog_at_centroids(
    cog_url: str,
    centroids: Dict[str, Tuple[float, float]],
    band_name: str,
    tid: int,
) -> List[Tuple[str, int, str, Optional[str], Optional[float], Optional[dict]]]:
    """Sample a Cloud-Optimized GeoTIFF at DGGS cell centroids.

    Uses rasterio's /vsicurl/ to read via HTTP range requests.
    Only fetches the COG tiles that contain our sample points.

    Args:
        cog_url: HTTP(S) URL to the COG file
        centroids: {dggid: (lon, lat)} mapping
        band_name: Band name for attr_key
        tid: Time identifier (Unix epoch seconds)

    Returns:
        List of cell tuples (dggid, tid, attr_key, value_text, value_num, value_json)
    """
    cells = []

    # Set GDAL/rasterio environment for cloud access
    env_options = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
        "GDAL_HTTP_MULTIPLEX": "YES",
        "GDAL_HTTP_VERSION": "2",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff",
    }

    # Prepend /vsicurl/ for HTTP access if needed
    read_url = cog_url
    if cog_url.startswith("http://") or cog_url.startswith("https://"):
        read_url = f"/vsicurl/{cog_url}"
    elif cog_url.startswith("s3://"):
        read_url = f"/vsis3/{cog_url[5:]}"

    try:
        with rasterio.Env(**env_options):
            with rasterio.open(read_url) as src:
                src_crs = src.crs
                nodata = src.nodata
                bounds = src.bounds

                # Build coordinate list for sampling
                sample_points = []
                zone_ids = []

                for zone_id, (lon, lat) in centroids.items():
                    # Transform to source CRS if needed
                    x, y = lon, lat
                    if src_crs and str(src_crs) not in ("EPSG:4326", "OGC:CRS84"):
                        xs, ys = transform_coords("EPSG:4326", src_crs, [lon], [lat])
                        x, y = xs[0], ys[0]

                    # Check if point is within raster bounds
                    if bounds.left <= x <= bounds.right and bounds.bottom <= y <= bounds.top:
                        sample_points.append((x, y))
                        zone_ids.append(zone_id)

                if not sample_points:
                    return cells

                # Use rasterio.sample() for efficient COG tile reading
                # This only fetches the tiles containing our sample points
                values = list(src.sample(sample_points, indexes=1))

                for zone_id, val_array in zip(zone_ids, values):
                    val = float(val_array[0]) if val_array is not None else None
                    if val is not None and nodata is not None and val == nodata:
                        continue
                    if val is not None and isfinite(val):
                        cells.append((zone_id, tid, band_name, None, val, None))

    except rasterio.errors.RasterioIOError as e:
        logger.error("Failed to read COG %s: %s", cog_url, str(e))
    except Exception as e:
        logger.error("Unexpected error sampling COG %s: %s", cog_url, str(e))

    return cells


async def _set_dataset_state(
    conn,
    dataset_id: uuid.UUID,
    status: str,
    metadata_patch: Optional[dict] = None,
):
    """Update dataset status and merge metadata."""
    await conn.execute(
        "UPDATE datasets SET metadata = metadata || $1, status = $2 WHERE id = $3",
        metadata_patch or {},
        status,
        dataset_id,
    )


async def _ensure_dataset(
    conn, dataset_id: Optional[str], name: str, user_id: Optional[str], dggs_name: str
) -> uuid.UUID:
    """Get existing dataset or create a new one."""
    if dataset_id:
        ds_uuid = uuid.UUID(dataset_id)
        exists = await conn.fetchval(
            "SELECT id FROM datasets WHERE id = $1", ds_uuid
        )
        if exists:
            return ds_uuid

    # Create new dataset
    new_id = uuid.uuid4()
    user_uuid = uuid.UUID(user_id) if user_id else None

    # Validate and create partition table name
    partition_name = f"cell_objects_{str(new_id).replace('-', '_')}"

    await conn.execute(
        "INSERT INTO datasets (id, name, dggs_name, status, created_by, metadata) "
        "VALUES ($1, $2, $3, 'processing', $4, '{}'::jsonb)",
        new_id, name, dggs_name, user_uuid,
    )

    # Create partition for this dataset
    await conn.execute(
        f'CREATE TABLE IF NOT EXISTS "{partition_name}" '
        f"PARTITION OF cell_objects FOR VALUES IN ('{new_id}')"
    )

    return new_id


async def _insert_cells(
    conn,
    dataset_id: str,
    rows: List[Tuple[str, int, str, Optional[str], Optional[float], Optional[dict]]],
):
    """Batch insert cell objects with upsert."""
    if not rows:
        return

    query = """
        INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_text, value_num, value_json)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (dataset_id, dggid, tid, attr_key) DO UPDATE
        SET value_text = EXCLUDED.value_text,
            value_num = EXCLUDED.value_num,
            value_json = EXCLUDED.value_json
    """
    chunk_size = 1000
    for i in range(0, len(rows), chunk_size):
        batch = [(dataset_id, *row) for row in rows[i: i + chunk_size]]
        await conn.executemany(query, batch)
