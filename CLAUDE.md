# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/claude-code) when working with code in this repository.

## Project Overview

TerraCube IDEAS is a Web GIS system implementing the **IDEAS (International Data Exchange & Access System) data model** on the **IVEA3H DGGS (Discrete Global Grid System)**. The architecture is "DGGS-only" — no server-side PostGIS geometry. All spatial operations use SQL table operations on DGGS cell IDs, with client-side rendering via DGGAL WASM.

**Key architectural principle:** Spatial operations (Buffer, Aggregate, Union, Intersection, Difference) create **new persistent datasets** rather than ephemeral results. All operations are database-centric using the `dgg_topology` table for traversal.

## Development Commands

### Infrastructure
```bash
# Start all services (postgres, redis, minio)
docker compose up -d
```

### Backend
```bash
cd backend
cp .env.example .env  # Configure DATABASE_URL, JWT_SECRET, etc.
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 4000
```

### Worker (Celery)
```bash
cd backend
source .venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```

### Frontend
```bash
cd frontend
npm install
npm run dev      # Dev server on port 5173
npm run build    # Production build
npm run test     # Vitest tests
```

### Database Setup
```bash
# Create tables
psql postgresql://ideas_user:ideas_password@localhost:5433/ideas -f backend/db/schema.sql

# Initialize topology (REQUIRED for buffer/aggregate operations)
python backend/app/init_db.py
python backend/app/scripts/populate_topology.py

# Optional: Load real world data
python backend/app/scripts/load_real_data.py
```

## Architecture

### Backend (FastAPI)

**Router structure** (`backend/app/routers/`):
- `auth.py` — Authentication (JWT)
- `datasets.py` — Dataset CRUD, cell lookup by viewport
- `uploads.py` — File staging (CSV/JSON/GeoTIFF) + ingestion jobs
- `ops.py` — **Persistent spatial operations** (intersection, union, difference, buffer, aggregate)
- `stats.py` — Zonal statistics
- `toolbox.py` — Legacy toolbox endpoints
- `topology.py` — DGGS topology queries (parent, neighbors, children)

**Services** (`backend/app/services/`):
- `spatial_engine.py` — Core spatial operations using DGGAL service
- `ingest.py` — Celery task for processing uploaded files
- `ops_service.py` — High-level operation orchestration

**Repositories** (`backend/app/repositories/`):
- `dataset_repo.py`, `cell_object_repo.py`, `user_repo.py`, `upload_repo.py`

### Database Schema

**Core tables:**
- `datasets` — Dataset metadata
- `cell_objects` — **IDEAS 5-tuple**: `(dataset_id, dggid, tid, attr_key, value)` — partitioned by dataset_id
- `dgg_topology` — Pre-computed neighbor/parent relationships for K-ring buffer and aggregation
- `uploads` — File staging records
- `users` — Authentication

**Key design:** No spatial types (PostGIS). All spatial queries use DGGS cell IDs and topology table joins.

### Frontend (Vite + React + Deck.gl)

**Core components:**
- `MapView.tsx` — Map component with Deck.gl + MapLibre GL, handles DGGS cell rendering and selection
- `DashboardPage.tsx` — Main dashboard
- `ToolboxPanel.tsx` — Spatial tools UI
- `LayerList.tsx` — Layer management

**State management:**
- `lib/store.ts` — Zustand store for layers (`addLayer`, `updateLayer`, `removeLayer`)

**Key libraries:**
- `dggal.ts` — DGGAL WASM wrapper for IVEA3H geometry generation
- `api.ts` / `api-hooks.ts` — API client with TanStack Query
- `spatialDb.ts` — IndexedDB caching for polygon geometries

**DGGAL WASM assets** served from `frontend/public/dggal/`:
- `dggal.js`, `libdggal.js`, `libdggal_c_fn.js.0.0.wasm`

### Data Flow

1. **Viewport rendering:** Frontend requests DGGS zones for current extent → Backend lists zones (using DGGAL or topology) → Frontend fetches cell attributes by dggid list → Frontend builds polygons via DGGAL WASM → Deck.gl renders

2. **Spatial operation:** User selects operation (e.g., Buffer) → Backend executes spatial op → New dataset created with result cells → Frontend adds as new layer

3. **File upload:** File staged to MinIO → Celery worker processes → Cells inserted to `cell_objects` → Dataset marked active

## Configuration

### Backend (`.env`)
```
DATABASE_URL=postgres://...
JWT_SECRET=...
CORS_ORIGIN=http://localhost:5173
MINIO_ENDPOINT=localhost
MINIO_PORT=9000
REDIS_HOST=localhost
```

### Frontend (`.env`)
```
VITE_API_URL=http://localhost:4000
```

## Important Notes

- The `dgg_topology` table must be populated before buffer/aggregate operations will work
- Dataset cell data is stored in partitioned tables (`cell_objects_{dataset_id}`)
- Frontend uses DGGAL WASM to generate polygon vertices — coordinates returned in radians, converted to degrees
- All spatial operations create new persistent datasets (not ephemeral results)
- GeoTIFF ingestion samples raster values at DGGS cell centroids
