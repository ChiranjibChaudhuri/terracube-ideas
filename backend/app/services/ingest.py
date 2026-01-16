import rasterio
import logging
import csv
import json
import os
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple
from app.dggal_utils import get_dggal_service
from app.db import get_db_pool

from app.celery_app import celery_app
import asyncio

logger = logging.getLogger(__name__)

@celery_app.task
def process_upload(
    upload_id: str,
    file_path: str,
    dataset_id: str,
    dggs_name: str = "IVEA3H",
    attr_key: Optional[str] = None,
    min_level: Optional[int] = None,
    max_level: Optional[int] = None,
    source_type: Optional[str] = None,
):
    asyncio.run(
        _process_upload_async(
            upload_id,
            file_path,
            dataset_id,
            dggs_name,
            attr_key,
            min_level,
            max_level,
            source_type,
        )
    )

def _normalize_value(raw_value: Any) -> Tuple[Optional[str], Optional[float], Optional[dict]]:
    if raw_value is None:
        return None, None, None
    if isinstance(raw_value, (dict, list)):
        return None, None, raw_value
    if isinstance(raw_value, (int, float)):
        return None, float(raw_value), None
    if isinstance(raw_value, str):
        trimmed = raw_value.strip()
        if not trimmed:
            return None, None, None
        try:
            return None, float(trimmed), None
        except ValueError:
            return trimmed, None, None
    return str(raw_value), None, None

def _parse_cell_record(record: Dict[str, Any], fallback_attr_key: str) -> Optional[Tuple[str, int, str, Optional[str], Optional[float], Optional[dict]]]:
    dggid = str(record.get("dggid") or record.get("dggId") or record.get("zone") or "").strip()
    if not dggid:
        return None

    attr_key = str(
        record.get("attr_key")
        or record.get("key")
        or record.get("attribute")
        or record.get("attr")
        or fallback_attr_key
        or ""
    ).strip()
    if not attr_key:
        return None

    tid_value = record.get("tid")
    if tid_value is None:
        tid_value = record.get("time")
    if tid_value is None:
        tid_value = 0
    try:
        tid = int(tid_value)
    except (TypeError, ValueError):
        tid = 0

    raw_value = record.get("value")
    if raw_value is None:
        raw_value = record.get("value_text")
    if raw_value is None:
        raw_value = record.get("value_num")
    if raw_value is None:
        raw_value = record.get("value_json")
    value_text, value_num, value_json = _normalize_value(raw_value)

    return dggid, tid, attr_key, value_text, value_num, value_json

async def _insert_cells(conn, dataset_id: str, rows: List[Tuple[str, int, str, Optional[str], Optional[float], Optional[dict]]]):
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

async def _update_dataset_metadata(conn, dataset_id: str, patch: Dict[str, Any]):
    existing = await conn.fetchrow("SELECT metadata FROM datasets WHERE id = $1", dataset_id)
    metadata = existing["metadata"] if existing and existing["metadata"] else {}
    metadata.update({k: v for k, v in patch.items() if v is not None})
    await conn.execute("UPDATE datasets SET metadata = $1 WHERE id = $2", metadata, dataset_id)

async def _set_upload_status(conn, upload_id: str, status: str, error: Optional[str] = None):
    await conn.execute(
        "UPDATE uploads SET status = $1, error = $2, updated_at = now() WHERE id = $3",
        status,
        error,
        upload_id,
    )

async def _process_upload_async(
    upload_id: str,
    file_path: str,
    dataset_id: str,
    dggs_name: str,
    attr_key: Optional[str],
    min_level: Optional[int],
    max_level: Optional[int],
    source_type: Optional[str],
):

    logger.info(f"Processing upload: {file_path} for dataset {dataset_id}")
    
    try:
        dataset_uuid = uuid.UUID(dataset_id)
        upload_uuid = uuid.UUID(upload_id)
        service = get_dggal_service()
        
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            await _set_upload_status(conn, str(upload_uuid), "processing")
            ext = os.path.splitext(file_path)[1].lower()

            if ext in (".tif", ".tiff"):
                with rasterio.open(file_path) as src:
                    bounds = src.bounds
                    # rasterio bounds: (left, bottom, right, top) -> (W, S, E, N)
                    # dgg bbox: S, W, N, E (per CLI -bbox option)
                    dgg_bbox = [bounds.bottom, bounds.left, bounds.top, bounds.right]

                    target_level = max_level or min_level or 9
                    logger.info(f"Listing zones for level {target_level} in bbox {dgg_bbox}")

                    zones = service.list_zones_bbox(target_level, dgg_bbox)

                    if zones:
                        data = src.read(1)
                        batch = []
                        raster_key = attr_key or "elevation"
                        for zone_id in zones:
                            centroid = service.get_centroid(zone_id)
                            row, col = src.index(centroid["lon"], centroid["lat"])

                            if 0 <= row < src.height and 0 <= col < src.width:
                                val = data[row, col]
                                if val != src.nodata:
                                    batch.append((
                                        zone_id,
                                        1,
                                        raster_key,
                                        None,
                                        float(val),
                                        None,
                                    ))

                        if batch:
                            await _insert_cells(conn, str(dataset_uuid), batch)
                            logger.info(f"Ingested {len(batch)} points for {dataset_uuid}")
                    else:
                        logger.warning("No zones found in bbox.")

                await _update_dataset_metadata(
                    conn,
                    str(dataset_uuid),
                    {
                        "min_level": min_level or target_level,
                        "max_level": max_level or target_level,
                        "attr_key": attr_key or "elevation",
                        "source_type": source_type or "raster",
                    },
                )
                resolved_min = min_level or target_level
                resolved_max = max_level or target_level
                if resolved_min == resolved_max:
                    await conn.execute(
                        "UPDATE datasets SET level = $1 WHERE id = $2",
                        resolved_min,
                        str(dataset_uuid),
                    )
                await conn.execute("UPDATE datasets SET status = $1 WHERE id = $2", "active", str(dataset_uuid))
                await _set_upload_status(conn, str(upload_uuid), "processed")
                logger.info("Processing complete")
                return

            if ext in (".csv", ".json"):
                if ext == ".csv":
                    with open(file_path, "r", newline="", encoding="utf-8") as handle:
                        reader = csv.DictReader(handle)
                        records = list(reader)
                else:
                    with open(file_path, "r", encoding="utf-8") as handle:
                        parsed = json.load(handle)
                    if isinstance(parsed, dict) and isinstance(parsed.get("cells"), list):
                        records = parsed["cells"]
                    elif isinstance(parsed, list):
                        records = parsed
                    else:
                        raise ValueError("JSON format not recognized. Expected array or {\"cells\": [...]} structure.")

                fallback_key = attr_key or "value"
                cells = []
                for record in records:
                    if not isinstance(record, dict):
                        continue
                    cell = _parse_cell_record(record, fallback_key)
                    if cell:
                        cells.append(cell)

                if not cells:
                    raise ValueError("No valid cell records found in file.")

                await _insert_cells(conn, str(dataset_uuid), cells)
                await _update_dataset_metadata(
                    conn,
                    str(dataset_uuid),
                    {
                        "min_level": min_level,
                        "max_level": max_level,
                        "attr_key": attr_key or fallback_key,
                        "source_type": source_type or "table",
                    },
                )
                if min_level is not None and max_level is not None and min_level == max_level:
                    await conn.execute(
                        "UPDATE datasets SET level = $1 WHERE id = $2",
                        min_level,
                        str(dataset_uuid),
                    )
                await conn.execute("UPDATE datasets SET status = $1 WHERE id = $2", "active", str(dataset_uuid))
                await _set_upload_status(conn, str(upload_uuid), "processed")
                logger.info(f"Ingested {len(cells)} rows for {dataset_uuid}")
                return

            raise ValueError("Unsupported file format. Use CSV, JSON, or GeoTIFF.")
            
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await _set_upload_status(conn, upload_id, "failed", str(e))
        except Exception:
            logger.error("Failed to update upload status.")
