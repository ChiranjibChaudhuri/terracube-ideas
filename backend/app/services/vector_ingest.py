
import os
import uuid
import logging
import asyncio
import json
from typing import List, Dict, Any, Optional
import fiona
from shapely.geometry import shape, Point, box
from app.dggal_utils import get_dggal_service
from app.db import get_db_pool
from app.models import Dataset
from sqlalchemy import text
from app.config import settings

logger = logging.getLogger(__name__)

def _process_feature(feature, service, resolution, attr_key, burn_attribute, new_id, cells_to_insert):
    geom = shape(feature['geometry'])
    val = 1.0
    val_text = None
    
    if burn_attribute and 'properties' in feature and burn_attribute in feature['properties']:
        raw_val = feature['properties'][burn_attribute]
        if isinstance(raw_val, (int, float)):
            val = float(raw_val)
        else:
            val_text = str(raw_val)
            val = 0.0 # Placeholder
    
    if geom.geom_type == 'Point':
        dggid = service.get_zone_at_point(geom.y, geom.x, resolution)
        if dggid:
            cells_to_insert.append({
                "dataset_id": str(new_id),
                "dggid": dggid,
                "tid": 0,
                "attr_key": attr_key,
                "value_num": val,
                "value_text": val_text
            })
    
    elif geom.geom_type in ['Polygon', 'MultiPolygon']:
        bounds = geom.bounds 
        bbox = [bounds[1], bounds[0], bounds[3], bounds[2]] 
        potential_zones = service.list_zones_bbox(resolution, bbox)
        for zid in potential_zones:
            centroid = service.get_centroid(zid)
            pt = Point(centroid['lon'], centroid['lat'])
            if geom.contains(pt):
                 cells_to_insert.append({
                    "dataset_id": str(new_id),
                    "dggid": zid,
                    "tid": 0,
                    "attr_key": attr_key,
                    "value_num": val,
                    "value_text": val_text
                })

async def ingest_vector_file(
    file_path: str,
    dataset_name: str,
    dggs_name: str = "IVEA3H",
    resolution: int = 10,
    attr_key: str = "value",
    burn_attribute: Optional[str] = None,
    dataset_id: Optional[str] = None
) -> str:
    """
    Ingests a vector file (Shapefile, GeoJSON) into DGGS cells.
    """
    service = get_dggal_service(dggs_name)
    new_id = dataset_id if dataset_id else str(uuid.uuid4())
    
    # ... (Pre-calculate cells logic remains same) ...
    
    cells_to_insert = []
    
    try:
        kwargs = {}
        if file_path.endswith('.json') or file_path.endswith('.geojson'):
            kwargs['driver'] = 'GeoJSON'
            
        with fiona.open(file_path, 'r', **kwargs) as source:
            logger.info(f"Opened vector file with Fiona: {file_path}. CRS: {source.crs}")
            for feature in source:
                _process_feature(feature, service, resolution, attr_key, burn_attribute, new_id, cells_to_insert)

    except Exception as e:
        logger.warning(f"Fiona ingest failed ({e}). Attempting JSON fallback.")
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            features = data.get('features', []) if isinstance(data, dict) else data
            if not isinstance(features, list):
                 # Handle list of features at root
                 features = data if isinstance(data, list) else []
            
            logger.info(f"Opened vector file with JSON (fallback). Found {len(features)} features.")
            
            for feature in features:
                 _process_feature(feature, service, resolution, attr_key, burn_attribute, new_id, cells_to_insert)
                 
        except Exception as e2:
             logger.error(f"JSON fallback also failed: {e2}")
             raise e



    # Batch Insert
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Upsert Dataset check
            # If we passed an ID, it might already exist. If not, insert.
            row = await conn.fetchrow("SELECT id, metadata FROM datasets WHERE id = $1", new_id)
            if not row:
                await conn.execute("""
                    INSERT INTO datasets (id, name, dggs_name, metadata)
                    VALUES ($1, $2, $3, $4)
                """, new_id, dataset_name, dggs_name, '{"type": "vector_import", "source": "file"}')
            else:
                 # Update status?
                 pass

            # Insert Cells
            if cells_to_insert:
                unique_cells = {}
                for c in cells_to_insert:
                    key = (c['dggid'], c['attr_key'])
                    unique_cells[key] = c
                
                final_cells = list(unique_cells.values())
                
                await conn.executemany("""
                    INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_num, value_text)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (dataset_id, dggid, tid, attr_key) DO UPDATE
                    SET value_num = EXCLUDED.value_num, value_text = EXCLUDED.value_text
                """, [(c['dataset_id'], c['dggid'], c['tid'], c['attr_key'], c['value_num'], c['value_text']) for c in final_cells])
                
                logger.info(f"Inserted {len(final_cells)} cells for vector layer {dataset_name}")
                
                # Update status + metadata (attr_key, min/max levels, source type)
                meta = row['metadata'] if row else {"type": "vector_import", "source": "file"}
                if meta and isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                meta = meta or {}
                existing_min = meta.get('min_level')
                existing_max = meta.get('max_level')
                new_min = resolution if existing_min is None else min(int(existing_min), resolution)
                new_max = resolution if existing_max is None else max(int(existing_max), resolution)
                meta.update({
                    "attr_key": attr_key,
                    "min_level": new_min,
                    "max_level": new_max,
                    "source_type": "vector"
                })
                level_value = new_min if new_min == new_max else None
                await conn.execute(
                    "UPDATE datasets SET status = 'ready', metadata = $1, level = $2 WHERE id = $3",
                    json.dumps(meta),
                    level_value,
                    new_id
                )
            else:
                logger.warning("No cells found intersecting features.")

    return str(new_id)
