# TerraCube IDEAS DGGS Web GIS

This repo is a minimal end-to-end demo of an IDEAS-style data model running on IVEA3H DGGS. The backend stores IDEAS 5-tuples in Postgres (no spatial types), and the frontend uses DGGAL WASM + Deck.gl to build DGGS geometry client-side.

## Architecture highlights
- **IDEAS data model**: `cell_objects` stores `(dggid, tid, key, value, dataset)` in a long table, mirroring the IDEAS 5-tuple.
- **DGGS only**: No server-side geometry or PostGIS. Spatial queries are table operations on `dggid` and attributes.
- **Database-Centric Spatial Engine**: All spatial operations (Buffer, Aggregate, Union, Intersection) are performed via SQL queries (JOINs, CTEs) on the `cell_objects` table.
- **Topology Table**: `dgg_topology` stores neighbor and parent relationships to enable spatial traversal (e.g., K-ring buffering) without in-memory calculation.
- **Client rendering**: DGGAL WASM generates IVEA3H polygon vertices in the browser.
- **OGC DGGS-style visualization**: The frontend lists DGGS zones for the current viewport extent and zoom, fetches matching cell attributes, then joins + renders locally.

## Repo layout
- `backend/`: FastAPI API, Postgres schema, Celery worker for ingestion.
- `backend/app/scripts/`: Database population scripts (e.g., `populate_topology.py`).
- `frontend/`: Vite + React + Deck.gl UI with GSAP/Framer Motion landing page and DGGS dashboard.
- `docker-compose.yml`: Postgres, Redis, MinIO.

## Quick start
1) Start infra:
```bash
docker compose up -d
```

2) Create tables:
```bash
psql postgresql://ideas_user:ideas_password@localhost:5433/ideas -f backend/db/schema.sql
```

3) **Initialize Topology** (Required for Buffer/Aggregate):
```bash
# Ensure specific python environment with dggal is used
# (e.g., inside backend container or local venv)
python backend/app/init_db.py
python backend/app/scripts/populate_topology.py
```
*Note: This generates neighbor constants for Levels 1-7 (~200k rows).*

4) **Load Real Data** (Optional - requires internet):
```bash
python backend/app/scripts/load_real_data.py
```
*Downloads and ingests World Countries vector dataset.*

5) Backend:
```bash
cd backend
cp .env.example .env
# Setup venv and install dependencies...
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 4000
```

5) Worker:
```bash
cd backend
source .venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```

6) Frontend:
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Spatial Operations (Persistent)
The system eschews on-the-fly "toolbox" calculations in favor of persistent Dataset operations.
All spatial tools create a **New Dataset** representing the result.

### Available Operations (`POST /api/ops/spatial`)
- **Intersection**: `A n B` (Avg values)
- **Union**: `A u B` (Merge sets)
- **Difference**: `A - B` (Spatial subtraction)
- **Buffer**: Expands cells by K-rings using `dgg_topology`.
- **Aggregate**: Groups cells to parent level (mean value) using `dgg_topology`.

### Upload format
The ingestion worker accepts CSV/JSON files with DGGS cell rows, or GeoTIFF rasters.

Sample files are available in `backend/db/sample_cells.csv` and `backend/db/sample_cells.json`.

### CSV
```csv
dggid,tid,key,value
W6H1,0,temperature,18.4
W6H2,0,temperature,19.1
```

### JSON
```json
[
  { "dggid": "W6H1", "tid": 0, "key": "temperature", "value": 18.4 },
  { "dggid": "W6H2", "tid": 0, "key": "temperature", "value": 19.1 }
]
```

## API overview
- `POST /api/auth/register`, `POST /api/auth/login`
- `GET /api/datasets`, `GET /api/datasets/:id`
- `GET /api/datasets/:id/cells`
- `POST /api/datasets/:id/lookup` (fetch by viewport dggid list)
- `POST /api/ops/query` (range/filter/aggregate ops)
- `POST /api/ops/spatial` (Persistent: Intersection, Union, Difference, Buffer, Aggregate)
- ~~`POST /api/toolbox/*`~~ (Deprecated in favor of persistent ops)
- `POST /api/stats/zonal_stats`
- `POST /api/uploads` (file staging + preprocess job)

## Local configuration
- Backend env vars in `backend/.env` (see `backend/.env.example`).
- Frontend API URL: `VITE_API_URL` in `frontend/.env` (defaults to `http://localhost:4000`).

## Raster ingestion
Upload GeoTIFF rasters via `/api/uploads` and provide `attrKey` + optional `minLevel`/`maxLevel` to control sampling resolution.

## DGGAL assets
The browser loads DGGAL WASM assets from `frontend/public/dggal`:
- `dggal.js` (JS wrapper)
- `libdggal.js` + `libdggal_c_fn.js.0.0.wasm` (runtime)

These are sourced from the DGGAL project and bundled locally for offline use.
