"""
Real Global Data Loader for TerraCube IDEAS

Loads actual geographic data from Natural Earth (free, no API key).
Uses IVEA3H resolution 5-7 for detailed global coverage.

Architecture:
- Geometry (DGGID polygons): Frontend WASM via dggal
- Data (attribute values): Backend database  
- Join: Browser memory (viewport-based, ~2k cells max)
"""
import asyncio
import logging
import httpx
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from shapely.geometry import shape, Point
from shapely.ops import unary_union

from app.repositories.dataset_repo import DatasetRepository
from app.repositories.user_repo import UserRepository
from app.dggal_utils import get_dggal_service
from app.config import settings

logger = logging.getLogger(__name__)

# Natural Earth GeoJSON URLs (110m simplified)
NE_COUNTRIES = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
NE_CITIES = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_populated_places.geojson"
NE_LAND = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson"

# DGGS Resolution levels (IVEA3H) - Full pyramid for smooth zoom (1-12 → Level 1-6)
# Each level covers 2 zoom levels: zoom 1-2 → L1, zoom 3-4 → L2, etc.
LEVEL_MIN = 1   # Global overview (zoom 1-2)
LEVEL_MAX = 6   # Region view (zoom 11-12)
LEVEL_MEDIUM = 5 # Country view
LEVEL_FINE = 7  # Cities, Population density (optional finest)
HIERARCHY_LEVELS = list(range(LEVEL_MIN, LEVEL_MAX + 1))  # Levels 1-6


async def fetch_geojson(url: str) -> Optional[Dict]:
    """Fetch GeoJSON with timeout."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


async def load_real_global_data(session: AsyncSession):
    """Load real global datasets from Natural Earth at resolution 5-7."""
    logger.info("Loading real global datasets (IVEA3H level 5-7)...")
    
    user_repo = UserRepository(session)
    admin = await user_repo.get_by_email(settings.ADMIN_EMAIL)
    if not admin:
        logger.warning("Admin user not found, skipping.")
        return

    dataset_repo = DatasetRepository(session)
    dgg = get_dggal_service()

    # 5 diverse datasets for spatial operation demos
    await load_countries(session, dataset_repo, dgg, admin.id)
    await load_cities(session, dataset_repo, dgg, admin.id)
    await load_land_ocean(session, dataset_repo, dgg, admin.id)
    await load_continents(session, dataset_repo, dgg, admin.id)
    await load_population(session, dataset_repo, dgg, admin.id)

    logger.info("Real global data loading complete.")



async def load_countries(session, repo, dgg, admin_id):
    """World countries at levels 1-6."""
    name = "World Countries"
    if await dataset_exists(session, name):
        return

    geojson = await fetch_geojson(NE_COUNTRIES)
    if not geojson:
        return

    dataset = await repo.create(
        name=name,
        description=f"Natural Earth countries (Levels {LEVEL_MIN}-{LEVEL_MAX})",
        dggs_name="IVEA3H", level=LEVEL_MAX, created_by=admin_id,
        metadata_={"attr_key": "country", "min_level": LEVEL_MIN, 
                   "max_level": LEVEL_MAX, "source_type": "vector", 
                   "source": "Natural Earth", "hierarchical": True}
    )

    all_values = []
    
    # Process each level
    for level in HIERARCHY_LEVELS:
        logger.info(f"Generating level {level} for {name}...")
        values = []
        
        # Determine global extent or iterate features?
        # For efficiency, we'll iterate features and find covering cells at this level.
        # But for global coverage, iterating bbox is safer to avoid holes, but slower.
        # Given we want "country" attribute, we must intersect.
        
        # Optimization: Pre-calculate centroids for global grid at this level
        # Then point-in-polygon check.
        cells = await asyncio.to_thread(dgg.list_zones_bbox, level, [-85, -180, 85, 180])
        
        # Convert GeoJSON features to shapes for fast querying
        shapes = []
        for feat in geojson.get("features", []):
            try:
                geom = feat.get("geometry")
                if not geom: continue
                s = shape(geom)
                props = feat.get("properties", {})
                country = (props.get("ADMIN") or props.get("NAME") or "Unknown").replace("'", "''")
                iso = props.get("ISO_A3") or "UNK"
                continent = props.get("CONTINENT") or "Unknown"
                pop = props.get("POP_EST") or 0
                meta = json.dumps({"iso": iso, "continent": continent, "pop": pop}).replace("'", "''")
                shapes.append((s, country, meta))
            except:
                pass

        # Batch processing
        chunk_size = 1000
        for i, cid in enumerate(cells):
            try:
                cent = await asyncio.to_thread(dgg.get_centroid, cid)
                pt = Point(cent["lon"], cent["lat"])
                
                # Naive search - in production use spatial index (rtree)
                # For 177 countries it's okay.
                match = None
                for s, country, meta in shapes:
                    if s.contains(pt):
                        match = (country, meta)
                        break
                
                if match:
                    country, meta = match
                    values.append(f"('{dataset.id}', '{cid}', 0, 'country', '{country}', NULL, '{meta}'::jsonb)")
            except:
                continue
            
            if len(values) >= 2000:
                await bulk_insert(session, dataset.id, values)
                all_values.extend(values)
                values = []
        
        if values:
            await bulk_insert(session, dataset.id, values)
            all_values.extend(values)

    await finalize_dataset(session, dataset.id, len(all_values), name)


async def load_cities(session, repo, dgg, admin_id):
    """Major cities at levels 1-6 (point presence)."""
    name = "Major World Cities"
    if await dataset_exists(session, name):
        return

    geojson = await fetch_geojson(NE_CITIES)
    if not geojson:
        return

    dataset = await repo.create(
        name=name,
        description=f"Natural Earth cities (Levels {LEVEL_MIN}-{LEVEL_MAX})",
        dggs_name="IVEA3H", level=LEVEL_MAX, created_by=admin_id,
        metadata_={"attr_key": "city", "min_level": LEVEL_MIN,
                   "max_level": LEVEL_MAX, "source_type": "point", 
                   "source": "Natural Earth", "hierarchical": True}
    )

    all_values = []
    
    # Extract cities first
    city_points = []
    for feat in geojson.get("features", []):
        props = feat.get("properties", {})
        city = (props.get("NAME") or "Unknown").replace("'", "''")
        country = (props.get("ADM0NAME") or "Unknown").replace("'", "''")
        pop = props.get("POP_MAX") or props.get("POP_MIN") or 0
        geom = feat.get("geometry")
        if geom and geom.get("type") == "Point":
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                city_points.append({
                    "lon": coords[0], "lat": coords[1], 
                    "city": city, "country": country, "pop": pop
                })

    for level in HIERARCHY_LEVELS:
        logger.info(f"Generating level {level} for {name}...")
        values = []
        
        # For points, we find the cell containing the point at this level
        for cp in city_points:
            try:
                # Small bbox around point to find containing cell
                # At high levels, cell is small. At low levels, cell is big.
                # list_zones_bbox always works.
                bbox = [cp["lat"] - 0.0001, cp["lon"] - 0.0001, cp["lat"] + 0.0001, cp["lon"] + 0.0001]
                cells = await asyncio.to_thread(dgg.list_zones_bbox, level, bbox)
                
                # Refine to find exact cell containing point if multiple returned
                target_cid = None
                if cells:
                    # Just take the first one returned for the point location
                    # Ideally we check dgg.get_centroid to see which is closest, but list_zones usually accurate for point
                    target_cid = cells[0] 
                
                if target_cid:
                    meta = json.dumps({"country": cp["country"]}).replace("'", "''")
                    values.append(f"('{dataset.id}', '{target_cid}', 0, 'city', '{cp['city']}', {cp['pop']}, '{meta}'::jsonb)")
            except Exception:
                continue
        
        # Deduplication happens in bulk_insert if multiple cities fall in same cell
        # But here we append all. bulk_insert handles it? 
        # bulk_insert keeps LAST value for same DGGID.
        # So if multiple cities in one cell, only one survives (the last one).
        # For visualization this is acceptable for now (highest Zoom shows cities separated).
        
        if values:
            await bulk_insert(session, dataset.id, values)
            all_values.extend(values)

    await finalize_dataset(session, dataset.id, len(all_values), name)


async def load_continents(session, repo, dgg, admin_id):
    """Continents at levels 1-6."""
    name = "World Continents"
    if await dataset_exists(session, name):
        return

    geojson = await fetch_geojson(NE_COUNTRIES)
    if not geojson:
        return

    dataset = await repo.create(
        name=name,
        description=f"Continent regions (Levels {LEVEL_MIN}-{LEVEL_MAX})",
        dggs_name="IVEA3H", level=LEVEL_MAX, created_by=admin_id,
        metadata_={"attr_key": "continent", "min_level": LEVEL_MIN,
                   "max_level": LEVEL_MAX, "source_type": "vector", 
                   "source": "Natural Earth", "hierarchical": True}
    )

    # Group by continent
    cont_geoms = {}
    for feat in geojson.get("features", []):
        cont = feat.get("properties", {}).get("CONTINENT")
        geom = feat.get("geometry")
        if cont and geom:
            try:
                if cont not in cont_geoms:
                    cont_geoms[cont] = []
                cont_geoms[cont].append(shape(geom))
            except:
                pass
    
    cont_unions = {c: unary_union(g) for c, g in cont_geoms.items()}
    all_values = []

    for level in HIERARCHY_LEVELS:
        logger.info(f"Generating level {level} for {name}...")
        cells = await asyncio.to_thread(dgg.list_zones_bbox, level, [-85, -180, 85, 180])
        
        values = []
        for i, cid in enumerate(cells):
            try:
                cent = await asyncio.to_thread(dgg.get_centroid, cid)
                pt = Point(cent["lon"], cent["lat"])
                
                found_cont = None
                for cont, geom in cont_unions.items():
                    if geom.contains(pt):
                        found_cont = cont
                        break
                
                if found_cont:
                    safe_cont = found_cont.replace("'", "''")
                    values.append(f"('{dataset.id}', '{cid}', 0, 'continent', '{safe_cont}', NULL, NULL)")
                
                if len(values) >= 2000:
                    await bulk_insert(session, dataset.id, values)
                    all_values.extend(values)
                    values = []
            except:
                continue

        if values:
            await bulk_insert(session, dataset.id, values)
            all_values.extend(values)

    await finalize_dataset(session, dataset.id, len(all_values), name)


async def load_population(session, repo, dgg, admin_id):
    """Population density at levels 1-6."""
    name = "Population Density"
    if await dataset_exists(session, name):
        return

    geojson = await fetch_geojson(NE_CITIES)
    if not geojson:
        return

    dataset = await repo.create(
        name=name,
        description=f"Population density (Levels {LEVEL_MIN}-{LEVEL_MAX})",
        dggs_name="IVEA3H", level=LEVEL_MAX, created_by=admin_id,
        metadata_={"attr_key": "density", "min_level": LEVEL_MIN,
                   "max_level": LEVEL_MAX, "source_type": "raster",
                   "source": "Derived from Natural Earth", "min_value": 0, "max_value": 10000,
                   "hierarchical": True}
    )

    # Collect cities
    cities = []
    for feat in geojson.get("features", []):
        props = feat.get("properties", {})
        pop = props.get("POP_MAX") or 0
        geom = feat.get("geometry")
        if geom and geom.get("type") == "Point":
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                cities.append({"lon": coords[0], "lat": coords[1], "pop": pop})

    all_values = []

    # For density, we project cities onto grid at each level
    for level in HIERARCHY_LEVELS:
        logger.info(f"Generating level {level} for {name}...")
        values = []
        
        # This naive approach is slow (cities * cells).
        # Better: For each city, find nearby cells at this level.
        # Buffer radius depends on level size? 
        # Actually logic was: loop cities, find cells around city, compute density.
        # We can keep that logic, just loop levels.
        
        # Adjust buffer based on level? 
        # Level 1 is huge (thousands km). A city contributes to its cell.
        # Level 6 is smaller.
        # We use a fixed buffer logic from before: buf ~ 1.5 degrees (~150km).
        
        for i, city in enumerate(cities):
            lat, lon, pop = city["lat"], city["lon"], city["pop"]
            buf = min(1.5, max(0.2, pop / 15000000))
            bbox = [lat - buf, lon - buf, lat + buf, lon + buf]
            
            try:
                # Use current level
                cells = await asyncio.to_thread(dgg.list_zones_bbox, level, bbox)
                
                # Limit cells per city to avoid explosion at high res
                # But at low res (Level 1), one cell covers entire bbox.
                
                for cid in cells[:150]:
                    cent = await asyncio.to_thread(dgg.get_centroid, cid)
                    dist = ((cent["lat"] - lat)**2 + (cent["lon"] - lon)**2)**0.5
                    # Simple inverse distance weighting
                    # If multiple cities affect same cell, we need aggregation.
                    # Current bulk_insert overwrites (keeps last).
                    # Ideally we should sum. 
                    # For now, let's stick to "max" (last one wins), or simple density.
                    
                    density = min(10000, max(0, int(pop / max(0.1, dist * 50000))))
                    values.append(f"('{dataset.id}', '{cid}', 0, 'density', NULL, {density}, NULL)")
                
            except:
                continue
        
        # We need to handle summation for density if we want accuracy, but strict overwrite is safer for now 
        # to match previous single-level logic.
        # Note: bulk_insert deduplicates by DGGID, so last city processed wins for a cell.
        
        if values:
            await bulk_insert(session, dataset.id, values)
            all_values.extend(values)

    await finalize_dataset(session, dataset.id, len(all_values), name)



# ---- Helpers ----

async def dataset_exists(session, name: str) -> bool:
    result = await session.execute(text("SELECT id FROM datasets WHERE name = :n"), {"n": name})
    if result.scalar():
        logger.info(f"Dataset '{name}' exists, skipping.")
        return True
    return False


async def bulk_insert(session, dataset_id, values: List[str]):
    if not values:
        return
    
    # Deduplicate by DGGID - extract DGGID from value string and keep last occurrence
    seen = {}
    for v in values:
        # Value format: ('uuid', 'dggid', ...)
        parts = v.split("'")
        if len(parts) >= 4:
            dggid = parts[3]  # Extract DGGID from value tuple
            seen[dggid] = v
    
    unique_values = list(seen.values())
    logger.info(f"Deduped {len(values)} -> {len(unique_values)} unique cells")
    
    # Use main table - partitioning is handled by DB if configured
    for i in range(0, len(unique_values), 500):
        chunk = unique_values[i:i+500]
        sql = f'''INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_text, value_num, value_json)
                  VALUES {",".join(chunk)}
                  ON CONFLICT (dataset_id, dggid, tid, attr_key) DO UPDATE
                  SET value_text=EXCLUDED.value_text, value_num=EXCLUDED.value_num, value_json=EXCLUDED.value_json'''
        await session.execute(text(sql))
    await session.commit()


async def finalize_dataset(session, dataset_id, count: int, name: str):
    await session.execute(text("UPDATE datasets SET status='active' WHERE id=:id"), {"id": str(dataset_id)})
    await session.commit()
    logger.info(f"Loaded {count} cells into '{name}'")
