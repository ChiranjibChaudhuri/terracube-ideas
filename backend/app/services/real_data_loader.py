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
    """World countries at level 5."""
    name = "World Countries"
    if await dataset_exists(session, name):
        return

    geojson = await fetch_geojson(NE_COUNTRIES)
    if not geojson:
        return

    dataset = await repo.create(
        name=name,
        description=f"Natural Earth countries (Level {LEVEL_MEDIUM})",
        dggs_name="IVEA3H", level=LEVEL_MEDIUM, created_by=admin_id,
        metadata_={"attr_key": "country", "min_level": LEVEL_MEDIUM, 
                   "max_level": LEVEL_MEDIUM, "source_type": "vector", "source": "Natural Earth"}
    )

    values = []
    for feat in geojson.get("features", []):
        props = feat.get("properties", {})
        country = (props.get("ADMIN") or props.get("NAME") or "Unknown").replace("'", "''")
        iso = props.get("ISO_A3") or "UNK"
        continent = props.get("CONTINENT") or "Unknown"
        pop = props.get("POP_EST") or 0
        
        geom = feat.get("geometry")
        if not geom:
            continue
            
        try:
            shp = shape(geom)
            bbox = [shp.bounds[1], shp.bounds[0], shp.bounds[3], shp.bounds[2]]
            cells = await asyncio.to_thread(dgg.list_zones_bbox, LEVEL_MEDIUM, bbox)
            
            for cid in cells[:3000]:
                cent = await asyncio.to_thread(dgg.get_centroid, cid)
                if shp.contains(Point(cent["lon"], cent["lat"])):
                    meta = json.dumps({"iso": iso, "continent": continent, "pop": pop}).replace("'", "''")
                    values.append(f"('{dataset.id}', '{cid}', 0, 'country', '{country}', NULL, '{meta}'::jsonb)")
        except Exception as e:
            logger.warning(f"Error: {e}")
            continue

    await bulk_insert(session, dataset.id, values)
    await finalize_dataset(session, dataset.id, len(values), name)


async def load_cities(session, repo, dgg, admin_id):
    """Major cities at level 7."""
    name = "Major World Cities"
    if await dataset_exists(session, name):
        return

    geojson = await fetch_geojson(NE_CITIES)
    if not geojson:
        return

    dataset = await repo.create(
        name=name,
        description=f"Natural Earth cities (Level {LEVEL_FINE})",
        dggs_name="IVEA3H", level=LEVEL_FINE, created_by=admin_id,
        metadata_={"attr_key": "city", "min_level": LEVEL_FINE,
                   "max_level": LEVEL_FINE, "source_type": "point", "source": "Natural Earth"}
    )

    values = []
    for feat in geojson.get("features", []):
        props = feat.get("properties", {})
        city = (props.get("NAME") or "Unknown").replace("'", "''")
        country = (props.get("ADM0NAME") or "Unknown").replace("'", "''")
        pop = props.get("POP_MAX") or props.get("POP_MIN") or 0
        
        geom = feat.get("geometry")
        if not geom or geom.get("type") != "Point":
            continue
        
        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue
        
        lon, lat = coords[0], coords[1]
        bbox = [lat - 0.15, lon - 0.15, lat + 0.15, lon + 0.15]
        
        try:
            cells = await asyncio.to_thread(dgg.list_zones_bbox, LEVEL_FINE, bbox)
            if cells:
                cid = cells[0]  # Closest cell to city center
                meta = json.dumps({"country": country}).replace("'", "''")
                values.append(f"('{dataset.id}', '{cid}', 0, 'city', '{city}', {pop}, '{meta}'::jsonb)")
        except Exception:
            continue

    await bulk_insert(session, dataset.id, values)
    await finalize_dataset(session, dataset.id, len(values), name)


async def load_land_ocean(session, repo, dgg, admin_id):
    """Land vs Ocean classification with hierarchical multi-level storage."""
    name = "Land and Ocean"

    # Pre-fetch GeoJSON to ensure availability
    geojson = await fetch_geojson(NE_LAND)
    if not geojson:
        logger.error(f"Failed to download {NE_LAND}. Skipping '{name}'.")
        return

    # Check if dataset exists and needs reloading
    result = await session.execute(text("SELECT id FROM datasets WHERE name = :n"), {"n": name})
    existing_id = result.scalar()

    if existing_id:
        # Check if it has Level 1 data (indication of multi-resolution)
        # We query for existence of any cells at Level 1.
        # Since we can't easily query by level in DB without decoding DGGID, we rely on checking if *any* Level 1 cells exist.
        # But we don't store level explicitly.
        # Strategy: list a few Level 1 zones and check if they exist in the dataset.

        l1_zones = await asyncio.to_thread(dgg.list_zones_bbox, LEVEL_MIN, [-85, -180, 85, 180])
        # Take a sample of 10 zones
        sample_zones = l1_zones[:10]

        placeholders = ",".join([f"'{z}'" for z in sample_zones])
        # We need to format safely, but here zones are alphanumeric safe strings from dggal

        # Check if any of these exist
        check_sql = f"SELECT 1 FROM cell_objects WHERE dataset_id = '{existing_id}' AND dggid IN ({placeholders}) LIMIT 1"
        found = await session.execute(text(check_sql))

        if found.scalar():
            # Level 1 data exists, assume dataset is healthy
            logger.info(f"Dataset '{name}' seems healthy (Level 1 data found). Skipping.")
            return
        else:
            logger.info(f"Dataset '{name}' exists but misses Level 1 data. Reloading...")
            await session.execute(text("DELETE FROM datasets WHERE id = :id"), {"id": existing_id})
            await session.commit()

    # Create dataset with multi-level metadata (levels 1-6)
    dataset = await repo.create(
        name=name,
        description=f"Land/Ocean classification (Levels {LEVEL_MIN}-{LEVEL_MAX})",
        dggs_name="IVEA3H", level=LEVEL_MAX, created_by=admin_id,
        metadata_={"attr_key": "surface", "min_level": LEVEL_MIN,
                   "max_level": LEVEL_MAX, "source_type": "vector", 
                   "source": "Natural Earth", "class_values": ["land", "ocean"],
                   "hierarchical": True}
    )

    # Create land geometry union
    land_geoms = []
    for feat in geojson.get("features", []):
        geom = feat.get("geometry")
        if geom:
            try:
                land_geoms.append(shape(geom))
            except:
                pass
    land_union = unary_union(land_geoms) if land_geoms else None

    global_bbox = [-85, -180, 85, 180]
    all_values = []

    # Iterate all levels independently
    for level in HIERARCHY_LEVELS:
        logger.info(f"Generating level {level} for {name}...")
        cells = await asyncio.to_thread(dgg.list_zones_bbox, level, global_bbox)

        level_values = []
        for i, cid in enumerate(cells):
            try:
                cent = await asyncio.to_thread(dgg.get_centroid, cid)
                pt = Point(cent["lon"], cent["lat"])
                surface = "land" if land_union and land_union.contains(pt) else "ocean"
                value_num = 1 if surface == "land" else 0

                level_values.append(f"('{dataset.id}', '{cid}', 0, 'surface', '{surface}', {value_num}, NULL)")

                if len(level_values) >= 2000:
                    await bulk_insert(session, dataset.id, level_values)
                    all_values.extend(level_values)
                    level_values = []

            except Exception as e:
                continue

        if level_values:
            await bulk_insert(session, dataset.id, level_values)
            all_values.extend(level_values)
            
        logger.info(f"Level {level} complete: {len(cells)} cells.")

    await finalize_dataset(session, dataset.id, len(all_values), name)


async def load_continents(session, repo, dgg, admin_id):
    """Continents at level 5."""
    name = "World Continents"
    if await dataset_exists(session, name):
        return

    geojson = await fetch_geojson(NE_COUNTRIES)
    if not geojson:
        return

    dataset = await repo.create(
        name=name,
        description=f"Continent regions (Level {LEVEL_MEDIUM})",
        dggs_name="IVEA3H", level=LEVEL_MEDIUM, created_by=admin_id,
        metadata_={"attr_key": "continent", "min_level": LEVEL_MEDIUM,
                   "max_level": LEVEL_MEDIUM, "source_type": "vector", "source": "Natural Earth"}
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

    # Get global cells
    cells = await asyncio.to_thread(dgg.list_zones_bbox, LEVEL_MEDIUM, [-85, -180, 85, 180])
    logger.info(f"Assigning {len(cells)} cells to continents...")

    values = []
    for i, cid in enumerate(cells):
        try:
            cent = await asyncio.to_thread(dgg.get_centroid, cid)
            pt = Point(cent["lon"], cent["lat"])
            
            for cont, geom in cont_unions.items():
                if geom.contains(pt):
                    safe_cont = cont.replace("'", "''")
                    values.append(f"('{dataset.id}', '{cid}', 0, 'continent', '{safe_cont}', NULL, NULL)")
                    break
            
            if i % 1000 == 0:
                logger.info(f"Processed {i}/{len(cells)}...")
        except:
            continue

    await bulk_insert(session, dataset.id, values)
    await finalize_dataset(session, dataset.id, len(values), name)


async def load_population(session, repo, dgg, admin_id):
    """Population density at level 7 (derived from city proximity)."""
    name = "Population Density"
    if await dataset_exists(session, name):
        return

    geojson = await fetch_geojson(NE_CITIES)
    if not geojson:
        return

    dataset = await repo.create(
        name=name,
        description=f"Population density (Level {LEVEL_FINE})",
        dggs_name="IVEA3H", level=LEVEL_FINE, created_by=admin_id,
        metadata_={"attr_key": "density", "min_level": LEVEL_FINE,
                   "max_level": LEVEL_FINE, "source_type": "raster",
                   "source": "Derived from Natural Earth", "min_value": 0, "max_value": 10000}
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

    logger.info(f"Generating density from {len(cities)} cities...")

    values = []
    for i, city in enumerate(cities):
        lat, lon, pop = city["lat"], city["lon"], city["pop"]
        buf = min(1.5, max(0.2, pop / 15000000))
        bbox = [lat - buf, lon - buf, lat + buf, lon + buf]
        
        try:
            cells = await asyncio.to_thread(dgg.list_zones_bbox, LEVEL_FINE, bbox)
            for cid in cells[:150]:
                cent = await asyncio.to_thread(dgg.get_centroid, cid)
                dist = ((cent["lat"] - lat)**2 + (cent["lon"] - lon)**2)**0.5
                density = min(10000, max(0, int(pop / max(0.1, dist * 50000))))
                values.append(f"('{dataset.id}', '{cid}', 0, 'density', NULL, {density}, NULL)")
            
            if i % 50 == 0:
                logger.info(f"Processed {i}/{len(cities)} cities...")
        except:
            continue

    await bulk_insert(session, dataset.id, values)
    await finalize_dataset(session, dataset.id, len(values), name)


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
