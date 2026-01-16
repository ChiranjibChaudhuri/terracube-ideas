# TerraCube IDEAS DGGS Web GIS

This repo is a minimal end-to-end demo of an IDEAS-style data model running on IVEA3H DGGS. The backend stores IDEAS 5-tuples in Postgres (no spatial types), and the frontend uses DGGAL WASM + Deck.gl to build DGGS geometry client-side.

## Architecture highlights
- **IDEAS data model**: `cell_objects` stores `(dggid, tid, key, value, dataset)` in a long table, mirroring the IDEAS 5-tuple.
- **DGGS only**: No server-side geometry or PostGIS. Spatial queries are table operations on `dggid` and attributes.
- **Client rendering**: DGGAL WASM generates IVEA3H polygon vertices in the browser.
- **OGC DGGS-style visualization**: The frontend lists DGGS zones for the current viewport extent and zoom, fetches matching cell attributes, then joins + renders locally (no vector tiles).
- **Staging pipeline**: Redis + Celery preprocess uploads into DGGS cell objects; raster ingestion samples centroids on the backend.

## Repo layout
- `backend/`: FastAPI API, Postgres schema, Celery worker for ingestion.
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

3) Backend:
```bash
cd backend
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 4000
```

4) Worker:
```bash
cd backend
source .venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```

5) Frontend:
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Upload format
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

Notes:
- `dggid` should be a DGGAL zone text ID (IVEA3H). The frontend converts this to geometry.
- `tid` defaults to 0 if not provided.
- `value` can be numeric or text.
- Uploads can optionally pass `datasetName`, `attrKey`, `minLevel`, `maxLevel`, and `sourceType` in the multipart form.

## API overview
- `POST /api/auth/register`, `POST /api/auth/login`
- `GET /api/datasets`, `GET /api/datasets/:id`
- `GET /api/datasets/:id/cells`
- `POST /api/datasets/:id/lookup` (fetch by viewport dggid list)
- `POST /api/ops/query` (range/filter/aggregate ops)
- `POST /api/ops/spatial` (intersection/zonal DGGS joins with resolution checks)
- `POST /api/ops/topology` (neighbors/parent/children/vertices)
- `POST /api/analytics/query` (set ops across datasets)
- `POST /api/toolbox/*` (buffer/union/intersection/difference/mask)
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
