
import rasterio
import logging
import os
import uuid
from typing import List, Tuple, Optional
from rasterio.warp import transform as transform_coords, transform_bounds
from app.dggal_utils import get_dggal_service
from app.db import get_db_pool

logger = logging.getLogger(__name__)

async def _insert_cells(conn, dataset_id: str, rows: List[Tuple]):
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
        batch = [(dataset_id, *row) for row in rows[i : i + chunk_size]]
        await conn.executemany(query, batch)

async def ingest_raster_file(
    file_path: str,
    dataset_name: str,
    dggs_name: str = "IVEA3H",
    attr_key: str = "value",
    min_level: int = 1,
    max_level: int = 7,  # Default to 7 for decent balance
    source_type: str = "raster",
    dataset_id: Optional[str] = None
) -> str:
    """
    Ingests a Raster file (GeoTIFF) into DGGS cells.
    """
    new_id = dataset_id if dataset_id else str(uuid.uuid4())
    logger.info(f"Ingesting raster {file_path} into dataset {dataset_name} ({new_id})")
    
    service = get_dggal_service(dggs_name)
    
    if min_level > max_level:
        min_level, max_level = max_level, min_level

    try:
        with rasterio.open(file_path) as src:
            data = src.read(1)
            src_crs = src.crs
            nodata = src.nodata
            bounds = src.bounds

            # dgg bbox: S, W, N, E (always in EPSG:4326)
            if src_crs and str(src_crs) not in ("EPSG:4326", "OGC:CRS84"):
                minx, miny, maxx, maxy = transform_bounds(
                    src_crs, "EPSG:4326",
                    bounds.left, bounds.bottom, bounds.right, bounds.top,
                    densify_pts=21
                )
                dgg_bbox = [miny, minx, maxy, maxx]
            else:
                dgg_bbox = [bounds.bottom, bounds.left, bounds.top, bounds.right]

            def to_dataset_coords(lon: float, lat: float):
                if not src_crs:
                    return lon, lat
                if str(src_crs) in ("EPSG:4326", "OGC:CRS84"):
                    return lon, lat
                xs, ys = transform_coords("EPSG:4326", src_crs, [lon], [lat])
                return xs[0], ys[0]

            pool = await get_db_pool()
            async with pool.acquire() as conn:
                # Upsert Dataset
                row = await conn.fetchrow("SELECT id FROM datasets WHERE id = $1", new_id)
                if not row:
                     await conn.execute("""
                        INSERT INTO datasets (id, name, dggs_name, metadata, status)
                        VALUES ($1, $2, $3, $4, 'processing')
                    """, new_id, dataset_name, dggs_name, '{"source_type": "raster", "source_file": "init_script"}')
                
                total_cells = 0
                for level in range(min_level, max_level + 1):
                    logger.info(f"Processing level {level}")
                    zones = service.list_zones_bbox(level, dgg_bbox)
                    if not zones:
                        continue
                        
                    batch = []
                    for zone_id in zones:
                        centroid = service.get_centroid(zone_id)
                        x, y = to_dataset_coords(centroid["lon"], centroid["lat"])

                        # If centroid falls outside raster bounds, clamp to nearest edge
                        if x < src.bounds.left or x > src.bounds.right or y < src.bounds.bottom or y > src.bounds.top:
                            x = min(max(x, src.bounds.left), src.bounds.right)
                            y = min(max(y, src.bounds.bottom), src.bounds.top)

                        try:
                            row, col = src.index(x, y)
                        except Exception:
                            continue

                        if 0 <= row < src.height and 0 <= col < src.width:
                            val = data[row, col]
                            if nodata is None or val != nodata:
                                # Skip very small values/nodata markers sometimes present
                                if val < -10000: # Common no-data in some DEMs
                                    continue
                                    
                                batch.append((
                                    zone_id,
                                    0,
                                    attr_key,
                                    None,
                                    float(val),
                                    None,
                                ))
                    
                    if batch:
                        await _insert_cells(conn, new_id, batch)
                        total_cells += len(batch)
                        logger.info(f"Ingested {len(batch)} points for level {level}")
                
                # Update Metadata
                await conn.execute("""
                    UPDATE datasets 
                    SET metadata = jsonb_set(
                        jsonb_set(
                            jsonb_set(COALESCE(metadata, '{}'::jsonb), '{min_level}', to_jsonb($1::int)), 
                            '{max_level}', to_jsonb($2::int)
                        ),
                        '{attr_key}', to_jsonb($3::text)
                    ),
                    status = 'ready',
                    level = CASE WHEN $1 = $2 THEN $1 ELSE NULL END
                    WHERE id = $4
                """, min_level, max_level, attr_key, new_id)
                
                logger.info(f"Raster ingestion complete. Total cells: {total_cells}")
                
    except Exception as e:
        logger.error(f"Raster ingest failed: {e}")
        raise e

    return new_id
