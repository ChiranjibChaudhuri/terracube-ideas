"""
Real Global Data Loader for TerraCube IDEAS

Downloads and ingests:
1. Natural Earth Vectors (Countries)
2. WorldClim Rasters (Elevation, Temperature)
"""
import asyncio
import logging
import os
import shutil
import zipfile
import requests
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.vector_ingest import ingest_vector_file
from app.services.raster_ingest import ingest_raster_file
from app.db import get_db_pool # We use pool directly for ingestors

logger = logging.getLogger(__name__)

# Data Sources Configuration
DATA_SOURCES = [
    {
        "name": "World Countries",
        "type": "vector",
        "url": "https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson",
        "file": "countries.geojson",
        "dggs": "IVEA3H",
        "min_lvl": 1,
        "max_lvl": 10
    },
    {
        "name": "Canada Boundaries",
        "type": "vector",
        "url": "https://raw.githubusercontent.com/johan/world.geo.json/master/countries/CAN.geo.json",
        "file": "CAN.geo.json",
        "dggs": "IVEA3H",
        "min_lvl": 1,
        "max_lvl": 13
    },
    {
        "name": "Dubai DEM (PlanetDEM 1s)",
        "type": "raster",
        "url": "https://demo.planetobserver.com/PlanetDEM_1s_Dubai.zip",
        "file": "PlanetDEM_1s_Dubai.zip",
        "target_tif": "PlanetDEM_1s_Dubai.tif",
        "attr": "elevation_m",
        "min_lvl": 1,
        "max_lvl": 15
    },
    {
        "name": "Kilimanjaro DEM (PlanetDEM 3s)",
        "type": "raster",
        "url": "https://demo.planetobserver.com/PlanetDEM_3s_Kilimandjaro.zip",
        "file": "PlanetDEM_3s_Kilimandjaro.zip",
        "target_tif": "PlanetDEM_3s_Kilimandjaro.tif",
        "attr": "elevation_m",
        "min_lvl": 1,
        "max_lvl": 15
    },
    {
        "name": "USGS DEM Sample (o41078a5)",
        "type": "raster",
        "url": "https://download.osgeo.org/geotiff/samples/usgs/o41078a5.tif",
        "file": "o41078a5.tif",
        "attr": "elevation_m",
        "min_lvl": 1,
        "max_lvl": 15
    },
    {
        "name": "USGS DEM Sample (i30dem)",
        "type": "raster",
        "url": "https://download.osgeo.org/geotiff/samples/usgs/i30dem.tif",
        "file": "i30dem.tif",
        "attr": "elevation_m",
        "min_lvl": 1,
        "max_lvl": 15
    },
    {
        "name": "Global Elevation (ETOPO1)",
        "type": "raster",
        "url": "https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO1/data/bedrock/grid_registered/georeferenced_tiff/ETOPO1_Bed_g_geotiff.zip",
        "file": "ETOPO1_Bed_g_geotiff.zip",
        "target_tif": "ETOPO1_Bed_g_geotiff.tif",
        "attr": "altitude",
        "min_lvl": 1,
        "max_lvl": 10
    },
    {
        "name": "Global Temperature (WorldClim)",
        "type": "raster",
        "url": "https://geodata.ucdavis.edu/climate/worldclim/2_1/base/wc2.1_10m_tavg.zip",
        "file": "wc2.1_10m_tavg.zip",
        "target_tif": "wc2.1_10m_tavg_01.tif", # January temp
        "attr": "temperature_jan",
        "min_lvl": 1,
        "max_lvl": 10
    },
    # Removed failing WorldPop source (404)
]


def calculate_backoff(attempt: int, base_delay: float = 2.0, max_delay: float = 60.0) -> float:
    """Calculate exponential backoff delay."""
    delay = base_delay * (2 ** attempt)
    return min(delay, max_delay)

async def download_file(url, filename, subdir="/tmp"):
    local_path = os.path.join(subdir, filename)
    if os.path.exists(local_path):
        logger.info(f"File {local_path} exists, skipping download.")
        return local_path
    
    logger.info(f"Downloading {url}...")
    loop = asyncio.get_event_loop()
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Use headers to mimic browser
            headers = {'User-Agent': 'Mozilla/5.0'}
            # Disable verify for some github raw domains in certain envs
            resp = await loop.run_in_executor(None, lambda: requests.get(url, headers=headers, verify=False, stream=True, timeout=30))
            
            if resp.status_code == 200:
                with open(local_path, "wb") as f:
                     for chunk in resp.iter_content(chunk_size=8192):
                         f.write(chunk)
                logger.info(f"Saved to {local_path}")
                return local_path
            else:
                logger.warning(f"Attempt {attempt+1} failed: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} error: {e}")
            
        if attempt < max_retries - 1:
            delay = calculate_backoff(attempt)
            logger.info(f"Retrying in {delay}s...")
            await asyncio.sleep(delay)
            
    logger.error(f"Failed to download {url} after {max_retries} attempts.")
    return None

def extract_zip(zip_path, target_file, extract_to="/tmp"):
    logger.info(f"Extracting {target_file} from {zip_path}")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            names = zip_ref.namelist()
            if target_file in names:
                zip_ref.extract(target_file, extract_to)
                return os.path.join(extract_to, target_file)
            else:
                logger.warning(f"{target_file} not found in zip. Available: {names}")
                return None
    except Exception as e:
        logger.error(f"Unzip failed: {e}")
        return None


async def load_real_global_data(session: AsyncSession = None):
    """
    Load real global datasets.
    Arguments:
        session: SQLAlchemy session (ignored, we use internal pool logic)
    """
    logger.info("Initializing Real Global Data Loading...")
    
    # Ensure DB pool is initialized if not already (main.py does init_db but maybe not pool?)
    # get_db_pool initializes lazy global _pool.
    pool = await get_db_pool()
    
    try:
        for ds in DATA_SOURCES:
            logger.info(f"--- Checking {ds['name']} ---")
            
            dataset_uuid = None
            needs_reingest = False
            
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT id, status, metadata FROM datasets WHERE name = $1", ds['name'])
                if row:
                    dataset_uuid = str(row['id'])
                    meta = row['metadata']
                    if meta and isinstance(meta, str):
                        try:
                            import json
                            meta = json.loads(meta)
                        except:
                            meta = {}
                    meta = meta or {}
                    current_min = meta.get('min_level', 0) or 0
                    current_max = meta.get('max_level', 0) or 0
                    target_min = ds.get('min_lvl', 0) or 0
                    target_max = ds.get('max_lvl', 0) or 0

                    if current_min != target_min or current_max != target_max:
                        logger.info(
                            f"Dataset '{ds['name']}' ready but outdated level (Current: {current_min}-{current_max}, Target: {target_min}-{target_max}). Re-ingesting."
                        )
                        needs_reingest = True
                        # Clean up old data for this dataset
                        table_name = f"cell_objects_{str(dataset_uuid).replace('-', '_')}"
                        await conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
                        await conn.execute("DELETE FROM datasets WHERE id = $1", dataset_uuid)
                        dataset_uuid = None # Reset to create new
                    elif row['status'] == 'ready':
                        logger.info(f"Dataset '{ds['name']}' already ready ({dataset_uuid}) at Level {current_max}. Skipping.")
                        continue
                    else:
                         logger.info(f"Dataset '{ds['name']}' exists ({dataset_uuid}) but not ready. Resuming/Updating.")
            
            # Download
            fpath = await download_file(ds['url'], ds['file'], subdir="/tmp") # Explicit subdir
            if not fpath:
                continue

            # Process (Unzip)
            ingest_path = fpath
            if ds['type'] == 'raster' and fpath.endswith('.zip'):
                extracted = extract_zip(fpath, ds['target_tif'])
                if extracted:
                    ingest_path = extracted
                else:
                    logger.error("Failed to extract target tif. Deleting corrupted zip.")
                    if os.path.exists(fpath):
                        os.remove(fpath)
                    continue
            
            # Ingest
            if ds['type'] == 'vector':
                # Loop through levels
                min_l = ds.get('min_lvl', 6)
                max_l = ds.get('max_lvl', 6)
                
                try:
                    # If first time (no uuid), let first call create it.
                    # If subsequent calls, pass the uuid.
                    current_ds_id = dataset_uuid 
                    
                    for lvl in range(min_l, max_l + 1):
                        logger.info(f"Ingesting vector {ds['name']} at level {lvl}...")
                        ds_id_out = await ingest_vector_file(
                            ingest_path,
                            ds['name'],
                            dggs_name="IVEA3H",
                            resolution=lvl,
                            attr_key="name",
                            burn_attribute="name",
                            dataset_id=current_ds_id
                        )
                        # Capture ID from first creation to reuse
                        if not current_ds_id:
                            current_ds_id = ds_id_out
                except Exception as e:
                    logger.error(f"Vector ingest failed for {ds['name']}: {e}")
                    if os.path.exists(ingest_path):
                        os.remove(ingest_path)
                        logger.info(f"Deleted potentially corrupted file: {ingest_path}")
                    continue
                        
            elif ds['type'] == 'raster':
                await ingest_raster_file(
                    ingest_path,
                    ds['name'],
                    dggs_name="IVEA3H",
                    attr_key=ds['attr'],
                    min_level=ds['min_lvl'],
                    max_level=ds['max_lvl'],
                    dataset_id=dataset_uuid
                )
                
            logger.info(f"Done processing {ds['name']}")

    except Exception as e:
        logger.error(f"Data loading error: {e}")
