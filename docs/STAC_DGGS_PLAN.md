# STAC-DGGS Integration Plan for TerraCube IDEAS

## Inspiration: Rasteret's "Index-First" Architecture

[Rasteret](https://github.com/terrafloww/rasteret) separates satellite data access into two planes:

- **Control Plane**: A queryable Parquet index storing scene metadata + COG tile offsets
- **Data Plane**: On-demand tile reads directly from cloud-hosted COGs (no GDAL overhead)

This achieves 8-21x speedups by eliminating repeated HTTP header parsing. The key insight: **cache metadata once, fetch pixels lazily**.

## The DGGS Adaptation: "Index-First DGGS Cell Access"

We adapt the same two-plane architecture but with a DGGS twist:

| Rasteret (Pixel-first) | TerraCube STAC (Cell-first) |
|---|---|
| Indexes COG tile offsets in Parquet | Indexes DGGS cell coverage per scene in Parquet |
| Fetches raw tiles for ML pipelines | Fetches tiles, samples at DGGS centroids |
| Output: numpy/xarray/TorchGeo tensors | Output: IDEAS cell objects in PostgreSQL |
| Collections = sets of scenes | Collections = DGGS-indexed scene catalogs |
| Filter by bbox, date, cloud cover | Filter by DGGS cells, date, cloud cover |

### Why This Matters for TerraCube

Current pipeline: Upload local file → rasterio → sample all cells → bulk insert. This means:
1. User must download GeoTIFFs manually
2. Entire rasters must be processed even for small AOIs
3. No catalog of available satellite data
4. No temporal scene management
5. No cloud-native data access

With STAC-DGGS integration:
1. Browse satellite catalogs (Sentinel-2, Landsat, NAIP, DEM) from the UI
2. Select AOI on the map → discover scenes covering those DGGS cells
3. Preview scene metadata without downloading anything
4. Ingest on-demand: only fetch the COG tiles that overlap requested DGGS cells
5. Temporal stacking: same cell across time → IDEAS `tid` dimension
6. Reproducible: same collection index = same results

---

## Architecture

```
                        ┌──────────────────────────┐
                        │   STAC API Endpoints     │
                        │  (Earth Search, PC, etc) │
                        └────────────┬─────────────┘
                                     │ pystac-client
                                     ▼
                        ┌──────────────────────────┐
                        │   STAC Discovery Layer   │
                        │  stac_discovery.py       │
                        │  - search(bbox, date,    │
                        │    cloud_cover, ...)      │
                        │  - list configured       │
                        │    catalogs              │
                        └────────────┬─────────────┘
                                     │
                                     ▼
                        ┌──────────────────────────┐
                        │   Collection Indexer     │
                        │  stac_indexer.py         │
                        │  - Parse COG headers     │
                        │  - Map scene bbox →      │
                        │    DGGS cell coverage    │
                        │  - Cache as GeoParquet   │
                        └────────────┬─────────────┘
                                     │
                         ┌───────────┼───────────┐
                         ▼           ▼           ▼
                   ┌──────────┐ ┌────────┐ ┌─────────┐
                   │ Parquet  │ │ MinIO  │ │ Postgres│
                   │ Index    │ │ Cache  │ │ Metadata│
                   │ (scene   │ │ (COG   │ │ (stac_  │
                   │  meta +  │ │ tile   │ │ collec- │
                   │  DGGS    │ │ cache) │ │ tions)  │
                   │  cells)  │ │        │ │         │
                   └──────────┘ └────────┘ └─────────┘
                         │           │           │
                         ▼           ▼           ▼
                   ┌──────────────────────────────────┐
                   │     DGGS Ingestion Engine        │
                   │  stac_ingest.py (Celery task)    │
                   │  - Select scenes by DGGS cells   │
                   │  - Fetch COG tiles (HTTP range)  │
                   │  - Sample at cell centroids      │
                   │  - Insert IDEAS cell objects     │
                   └──────────────┬───────────────────┘
                                  │
                                  ▼
                   ┌──────────────────────────────────┐
                   │    Existing TerraCube Engine      │
                   │  cell_objects → spatial ops →     │
                   │  analysis algorithms → viz        │
                   └──────────────────────────────────┘
```

---

## Data Model

### New Tables

```sql
-- STAC catalog configurations (which STAC APIs are available)
CREATE TABLE stac_catalogs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,       -- e.g. "earth-search-v1"
    api_url     TEXT NOT NULL,              -- e.g. "https://earth-search.aws.element84.com/v1"
    catalog_type TEXT NOT NULL DEFAULT 'api', -- 'api' or 'static'
    auth_type   TEXT,                       -- null, 'aws', 'planetary_computer', 'earthdata'
    collections JSONB,                      -- available STAC collection IDs
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Indexed STAC collections (user-created from STAC searches)
CREATE TABLE stac_collections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    catalog_id      UUID REFERENCES stac_catalogs(id),
    stac_collection TEXT NOT NULL,          -- STAC collection ID (e.g. "sentinel-2-l2a")
    bbox            FLOAT8[4],             -- search bounding box
    date_start      DATE,
    date_end        DATE,
    query_params    JSONB,                 -- cloud_cover_lt, etc.
    scene_count     INT DEFAULT 0,
    index_path      TEXT,                   -- path to Parquet index in MinIO
    status          TEXT DEFAULT 'indexing', -- indexing, ready, failed
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Individual scenes within a collection
CREATE TABLE stac_scenes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id   UUID REFERENCES stac_collections(id) ON DELETE CASCADE,
    stac_item_id    TEXT NOT NULL,          -- STAC item ID
    datetime        TIMESTAMPTZ,
    cloud_cover     FLOAT,
    bbox            FLOAT8[4],
    bands           JSONB,                 -- {band_name: {href, dtype, nodata, ...}}
    properties      JSONB,                 -- additional STAC properties
    dggs_coverage   TEXT[],                -- array of top-level DGGS cell IDs covered
    ingested        BOOLEAN DEFAULT FALSE,
    dataset_id      UUID REFERENCES datasets(id), -- linked IDEAS dataset (when ingested)
    UNIQUE(collection_id, stac_item_id)
);
```

### How It Maps to IDEAS

```
STAC Scene (1 datetime, N bands)
  ↓ sample at DGGS centroids
IDEAS Cell Objects:
  - dataset_id  = from stac_collection or per-scene dataset
  - dggid       = DGGS cell ID (IVEA3H)
  - tid         = scene datetime (epoch or index)
  - attr_key    = band name (e.g. "B04", "B08", "NDVI")
  - value_num   = sampled pixel value
```

This maps cleanly: each STAC scene becomes a time-slice (`tid`) in the IDEAS model, with each band as a separate `attr_key`.

---

## Implementation Plan

### Phase 1: STAC Discovery Layer

**New files:**
- `backend/app/services/stac_discovery.py` — STAC API search wrapper
- `backend/app/routers/stac.py` — REST endpoints for STAC operations

**Endpoints:**
```
GET  /api/stac/catalogs              — List configured STAC catalogs
GET  /api/stac/catalogs/{id}/search  — Search STAC catalog (bbox, date, cloud_cover)
POST /api/stac/collections           — Create a DGGS-indexed collection from search
GET  /api/stac/collections           — List user's STAC collections
GET  /api/stac/collections/{id}      — Collection details + scenes
```

**Implementation:**
```python
# stac_discovery.py
from pystac_client import Client

class StacDiscovery:
    """Discover and search STAC catalogs."""

    BUILTIN_CATALOGS = {
        "earth-search-v1": {
            "api_url": "https://earth-search.aws.element84.com/v1",
            "collections": ["sentinel-2-l2a", "landsat-c2-l2", "cop-dem-glo-30"],
        },
        "planetary-computer": {
            "api_url": "https://planetarycomputer.microsoft.com/api/stac/v1",
            "auth_type": "planetary_computer",
            "collections": ["sentinel-2-l2a", "landsat-c2-l2", "naip", "alos-dem"],
        },
    }

    async def search(self, catalog_id, collection, bbox, date_range,
                     cloud_cover_lt=None, max_items=100):
        """Search STAC API and return scene metadata."""
        # Uses pystac-client
        # Returns list of scene dicts with bbox, datetime, bands, thumbnails

    async def get_scene_preview(self, catalog_id, item_id):
        """Get thumbnail/quicklook for a scene."""
```

**Dependencies to add:**
```
pystac-client>=0.7.0
pyarrow>=14.0.0
```

### Phase 2: Collection Indexer (DGGS Coverage Mapping)

**New files:**
- `backend/app/services/stac_indexer.py` — Build DGGS-indexed collections

**What it does:**
1. Take STAC search results
2. For each scene: compute which DGGS cells (at a chosen level) the scene bbox covers
3. Store this DGGS coverage index alongside scene metadata
4. Cache the full index as a Parquet file in MinIO

```python
# stac_indexer.py
class DGGSCollectionIndexer:
    """Index STAC scenes by DGGS cell coverage."""

    async def build_collection(self, catalog_id, stac_collection,
                                bbox, date_range, name, **filters):
        """
        1. Search STAC API
        2. For each scene:
           - Compute DGGS cell coverage at overview level (e.g. level 4-5)
           - Parse COG band metadata (URLs, dtype, nodata)
        3. Store scene records in stac_scenes table
        4. Export Parquet index to MinIO
        5. Return collection metadata
        """

    def _compute_dggs_coverage(self, bbox, level=5):
        """Map a scene bbox to the DGGS cells it covers."""
        # Uses dggal_service.list_zones_bbox(level, bbox)
        # Returns list of DGGS cell IDs

    async def _parse_band_info(self, stac_item):
        """Extract band URLs and metadata from STAC item."""
        # Maps STAC asset keys to standard band names
        # Stores href, dtype, nodata per band
```

**Key design decision: Coverage level**
- We compute DGGS coverage at a coarse level (e.g. level 4-5) for fast spatial indexing
- Actual ingestion samples at the user-requested resolution (level 6-10)
- This is analogous to rasteret caching COG tile tables vs fetching actual pixels

### Phase 3: On-Demand DGGS Ingestion

**New files:**
- `backend/app/services/stac_ingest.py` — Celery tasks for COG→DGGS sampling

**What it does:**
1. User selects scenes from a collection to ingest
2. For each scene + band:
   - Fetch COG tiles that overlap the target DGGS cells (HTTP range requests)
   - Sample raster values at DGGS cell centroids
   - Insert as IDEAS cell objects
3. Create/update dataset with temporal slices

```python
# stac_ingest.py
@celery_app.task
def ingest_stac_scenes(collection_id, scene_ids, target_level, bands, dataset_name):
    """
    Ingest selected STAC scenes into IDEAS cell objects.

    1. Create target dataset
    2. For each scene:
       a. Determine DGGS cells at target_level within scene bbox
       b. For each band:
          - Open COG via rasterio with vsicurl (no download)
          - Sample at cell centroids
          - Batch insert cell objects with:
            - tid = scene datetime (epoch seconds)
            - attr_key = band name
            - value_num = sampled value
    3. Mark scenes as ingested, link to dataset
    """
```

**Cloud-native access (no download):**
```python
import rasterio
from rasterio.session import AWSSession

# Read directly from S3 via HTTP range requests
with rasterio.open(cog_url) as src:
    # Only fetches the tiles that contain our sample points
    values = list(src.sample([(lon, lat) for lon, lat in centroids]))
```

This is the key optimization from rasteret: we don't download the whole GeoTIFF. We use `rasterio.sample()` which reads only the COG tiles containing our centroid points via HTTP range requests.

### Phase 4: Frontend Integration

**New components:**
- `StacBrowser.tsx` — Browse STAC catalogs and search for data
- `SceneList.tsx` — View and filter discovered scenes
- `CollectionPanel.tsx` — Manage STAC collections
- Integration with existing `ToolboxPanel.tsx` and `MapView.tsx`

**UI Flow:**
```
1. User clicks "Add Data" → STAC Browser opens
2. Select catalog (Earth Search, Planetary Computer, etc.)
3. Draw AOI on map (or use current viewport)
4. Set date range, cloud cover filter
5. See scene results with thumbnails + metadata
6. Preview scene coverage as DGGS cells on map
7. Select scenes → Choose bands + resolution
8. Click "Ingest" → Background task creates IDEAS dataset
9. New layer appears on map when done
```

### Phase 5: Advanced Features

**5a. Temporal Stacking**
- Ingest multiple scenes of the same area over time
- Each scene becomes a different `tid` value
- Enables: time series analysis, change detection (already in our engine)

**5b. Virtual Collections (Lazy Evaluation)**
- Don't ingest immediately; compute DGGS values on-the-fly
- When user views cells: fetch COG tiles → sample → return values
- Only persist when user explicitly saves
- Trade-off: slower per-request but zero storage cost

**5c. Band Math / Derived Indices**
- Compute NDVI, EVI, NDWI during ingestion
- Formula engine: `NDVI = (B08 - B04) / (B08 + B04)`
- Store derived values as additional `attr_key` entries

**5d. Mosaic Engine**
- Multiple scenes cover the same area
- Select "best pixel" per DGGS cell (lowest cloud cover, most recent)
- Creates a cloud-free composite dataset

**5e. GeoParquet Export/Import**
- Export DGGS collections as GeoParquet (with DGGS cell IDs as index)
- Import GeoParquet collections from other DGGS systems
- Interoperability with the broader DGGS ecosystem

---

## Pre-configured STAC Catalogs

| Catalog | API URL | Key Collections | Auth |
|---|---|---|---|
| Element84 Earth Search v1 | `earth-search.aws.element84.com/v1` | sentinel-2-l2a, landsat-c2-l2, cop-dem-glo-30 | None (public) |
| Microsoft Planetary Computer | `planetarycomputer.microsoft.com/api/stac/v1` | sentinel-2-l2a, landsat-c2-l2, naip, alos-dem | SAS token |
| NASA CMR STAC | `cmr.earthdata.nasa.gov/stac` | Various NASA datasets | EarthData login |
| USGS STAC | `landsatlook.usgs.gov/stac-server` | Landsat | None |

---

## Implementation Sequence

```
Phase 1 (STAC Discovery)         ~3 days
  ├─ stac_catalogs table + seed data
  ├─ stac_discovery.py service
  ├─ stac.py router (search + list endpoints)
  └─ Frontend: StacBrowser basic UI

Phase 2 (Collection Indexer)      ~3 days
  ├─ stac_collections + stac_scenes tables
  ├─ stac_indexer.py service
  ├─ DGGS coverage computation
  ├─ Parquet index generation (MinIO)
  └─ Frontend: SceneList + preview

Phase 3 (DGGS Ingestion)          ~4 days
  ├─ stac_ingest.py Celery task
  ├─ Cloud-native COG access (vsicurl)
  ├─ Multi-band sampling
  ├─ Temporal tid mapping
  └─ Frontend: Ingest controls + progress

Phase 4 (Frontend Polish)         ~3 days
  ├─ Full STAC browser with filters
  ├─ Scene thumbnail previews
  ├─ Coverage overlay on map
  ├─ Band selection + resolution picker
  └─ Collection management panel

Phase 5 (Advanced)                ~5 days
  ├─ Band math / derived indices
  ├─ Temporal stacking
  ├─ Mosaic engine
  ├─ Virtual collections
  └─ GeoParquet export
```

---

## Dependencies

**Python (backend):**
```
pystac-client>=0.8.0     # STAC API search
pyarrow>=14.0.0          # Parquet I/O
geopandas>=0.13.0        # GeoParquet support
planetary-computer       # Optional: Planetary Computer auth
boto3                    # Optional: AWS requester-pays
```

**Existing (already available):**
```
rasterio                 # COG reading (already in requirements)
asyncpg                  # Database (already used)
celery                   # Task queue (already used)
minio                    # Object storage (already configured)
```

---

## Key Design Decisions

### 1. Parquet Index vs. Database-Only
**Decision: Hybrid** — Store scene metadata in PostgreSQL for querying, export full index as Parquet to MinIO for bulk operations and sharing. This gives us the best of both worlds: SQL queryability for the API layer, and Parquet efficiency for batch ingestion.

### 2. Coverage Level
**Decision: Level 5 for indexing, user-chosen for ingestion.** Level 5 IVEA3H cells are ~100km across, providing a coarse spatial index that maps scenes to regions without excessive storage. Actual data is ingested at finer resolutions (typically level 7-10).

### 3. COG Access Strategy
**Decision: Cloud-native via vsicurl/HTTP range requests.** Following rasteret's approach, we never download full GeoTIFFs. Rasterio's `sample()` method with `/vsicurl/` reads only the COG tiles containing our centroid points. For frequently accessed data, we cache tiles in MinIO.

### 4. Temporal Mapping
**Decision: tid = Unix epoch seconds of scene datetime.** This preserves temporal ordering and enables our existing temporal analysis tools. Alternative considered: sequential integer — rejected because it loses absolute time information.

### 5. Band Storage
**Decision: One attr_key per band.** Each spectral band (B04, B08, etc.) becomes a separate `attr_key` in the IDEAS model. Derived indices (NDVI) are stored as additional attr_keys. This keeps the model flat and queryable.

---

## Comparison: Before vs. After

| Capability | Current | With STAC-DGGS |
|---|---|---|
| Data discovery | Manual file download | Browse STAC catalogs in UI |
| Data access | Upload local files | Stream from cloud COGs |
| AOI selection | Entire file processed | Only requested DGGS cells |
| Temporal data | Single snapshot | Multi-temporal stacking |
| Band access | One value per upload | Multi-band per scene |
| Reproducibility | Depends on local file | STAC collection ID + params |
| Storage cost | Full raster → DB | Only sampled cell values |
| Latency | Upload + full processing | Targeted COG tile reads |
| Catalog | None | Pre-configured + custom |
