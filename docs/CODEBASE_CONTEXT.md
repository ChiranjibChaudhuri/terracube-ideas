# TerraCube IDEAS Codebase Context

Last reviewed against the repository on 2026-03-16.

## 1. What This Repo Is

TerraCube IDEAS is a DGGS-first Web GIS platform built around the IDEAS long-table data model:

- Backend: FastAPI + SQLAlchemy async + raw asyncpg + Celery
- Database: PostgreSQL without PostGIS geometry types
- Spatial model: DGGS cell IDs plus a precomputed `dgg_topology` table
- Frontend: Vite + React + Deck.gl + MapLibre
- Geometry generation: DGGAL on both backend and frontend

The core idea is consistent across the repo:

- persist DGGS cell attributes in `cell_objects`
- do spatial work as DGGS/topology/database operations
- generate polygons client-side for rendering

## 2. Current Mental Model

There are two different maturity levels in the codebase:

- The main product path is real: auth, datasets, uploads, viewport rendering, persistent spatial ops, topology-backed lookups, and STAC search/index/ingest.
- Several adjacent capabilities are present but lighter-weight or partially scaffolded: temporal analysis, prediction/ML, some collaboration features, some advanced analysis, and parts of the test/docs story.

The repo is best understood as a solid DGGS platform core with several expansion modules in different states of completion.

## 3. Runtime Architecture

### Backend startup

`backend/app/main.py` is the backend entrypoint.

At startup it:

- validates settings from `backend/app/config.py`
- runs `init_db()`, which executes `backend/db/schema.sql`
- seeds an admin user via `seed_admin()`
- starts a background result-cleanup loop
- registers all routers
- exposes Prometheus metrics
- optionally serves the built frontend from `frontend/dist`

Important consequence:

- runtime initialization still depends on `schema.sql`, not Alembic migrations

### Worker runtime

`backend/app/celery_app.py` defines a Redis-backed Celery app.

The worker is used for:

- file ingestion from uploads
- STAC scene ingestion

### Frontend runtime

`frontend/src/main.tsx` boots React Query and React Router.

`frontend/src/App.tsx` exposes:

- `/` landing page
- `/login`
- `/dashboard`
- `/workbench`

`/dashboard` is the main application UI. `/workbench` is a secondary/older analyst-style workspace.

## 4. Data Model

### Core tables

The main operational tables are:

- `users`
- `datasets`
- `cell_objects`
- `uploads`
- `dgg_topology`
- `stac_catalogs`
- `stac_collections`
- `stac_scenes`

### `cell_objects`

This is the core IDEAS-like long table.

Conceptually each row is:

- dataset
- DGGS cell (`dggid`)
- temporal id (`tid`)
- attribute key (`attr_key`)
- value stored in `value_num`, `value_text`, or `value_json`

The table is partitioned by `dataset_id`.

`backend/app/repositories/dataset_repo.py` creates a dataset-specific partition when a dataset is created.

### `dgg_topology`

This table is essential for topology-driven operations. It stores:

- `dggid`
- `neighbor_dggid`
- `parent_dggid`
- `level`

It is required for:

- buffer
- aggregate/coarsening
- propagation-style operations
- most neighborhood-based analysis

If topology is empty, those features degrade or fail.

## 5. Backend Structure

### Routers

Primary routers under `backend/app/routers/`:

- `auth.py`: JWT auth, register/login/me, admin user management
- `datasets.py`: dataset listing, details, creation, cell listing, lookup, export
- `uploads.py`: file upload entrypoint
- `upload_status.py`: polling upload/job status
- `topology.py`: low-level DGGS operations and viewport zone listing
- `ops.py`: query ops and persistent spatial ops
- `toolbox.py`: older in-memory/transient DGGS tools
- `stats.py`: simple zonal stats
- `stats_enhanced.py`: richer stats, correlation, hotspot analysis
- `spatial_analysis.py`: Moran's I, LISA, DBSCAN, pathing, density, flow
- `stac.py`: STAC catalog search, collection indexing, ingestion
- `annotations.py`: collaborative annotation endpoints
- `temporal.py`: temporal query/aggregation and CA endpoints
- `prediction.py`: prediction and fire-spread endpoints

### Service layer

Useful service split:

- `ops_service.py`: persistent spatial dataset creation
- `spatial_engine.py`: in-memory DGGAL-based set/topology operations
- `ingest.py`, `vector_ingest.py`, `raster_ingest.py`: file ingestion
- `stac_discovery.py`, `stac_indexer.py`, `stac_ingest.py`: STAC pipeline
- `zonal_stats.py`: enhanced stats engine
- `spatial_analysis.py`: advanced neighborhood/statistical analysis
- `temporal.py`: temporal and CA services
- `prediction.py`: prediction service, currently mostly simulated/scaffolded
- `annotations.py`: collaborative annotations
- `result_cleanup.py`: TTL cleanup of operation outputs

### Persistence style

The backend mixes two DB access patterns:

- SQLAlchemy async sessions for most application logic
- raw asyncpg pool for some startup and ingestion paths

That split matters when debugging transaction visibility and initialization order.

## 6. Main Product Flows

### Viewport rendering flow

This is the most important frontend-backend interaction.

1. `frontend/src/components/MapView.tsx` computes a DGGS level from zoom or fixed settings.
2. It calls `POST /api/topology/list_zones` to ask the backend for zone IDs in the current extent.
3. It calls `POST /api/datasets/{id}/lookup` to fetch attributes for those `dggid`s.
4. The frontend resolves DGGS polygons through `frontend/src/lib/dggal.ts`.
5. Deck.gl renders polygons with color ramps and opacity from layer state.

Design consequence:

- the backend is authoritative for which zones exist in a viewport
- the frontend is authoritative for polygon generation and rendering

### Persistent spatial operation flow

1. UI action comes from `ToolboxPanel.tsx`.
2. Frontend calls `POST /api/ops/spatial`.
3. `OpsService` validates datasets and topology prerequisites.
4. A new dataset record is created.
5. SQL inserts result rows into `cell_objects`.
6. The result dataset is shown as another layer.

Important detail:

- these are mostly persistent dataset-creating operations, not ephemeral overlays

### Upload ingestion flow

1. `POST /api/uploads`
2. Backend stores file under `UPLOAD_DIR`
3. Dataset is created or reused
4. Raster/CSV/JSON path uses Celery task `process_upload`
5. Vector files are currently kicked off with an in-process async task
6. Ingestion writes cell rows into `cell_objects`

### STAC flow

1. Frontend `StacBrowser.tsx` searches configured catalogs
2. `stac.py` calls `StacDiscovery`
3. `DGGSCollectionIndexer` stores searchable scene collections and DGGS coverage
4. Selected scenes are ingested asynchronously through Celery
5. Ingested scenes create or append to IDEAS datasets with temporal values in `tid`

This is one of the more substantial newer modules in the repo.

## 7. Frontend Structure

### App state

`frontend/src/lib/store.ts` keeps layer state in Zustand.

Each layer tracks:

- visibility
- opacity
- origin (`dataset` or `operation`)
- dataset linkage
- styling metadata such as color ramp and min/max values

### Main UI files

- `pages/DashboardPage.tsx`: primary app shell
- `components/MapView.tsx`: viewport loading, polygon resolution, selection overlays
- `components/DatasetSearch.tsx`: dataset/result picker
- `components/LayerList.tsx`: loaded layer management
- `components/ToolboxPanel.tsx`: styling + tool execution
- `components/StacBrowser.tsx`: STAC catalog workflow
- `pages/Workbench.tsx`: alternate workspace with preloaded polygon flow

### DGGAL client wrapper

`frontend/src/lib/dggal.ts`:

- lazy-loads the WASM assets from `frontend/public/dggal`
- converts DGGAL radians to degrees
- caches polygons in memory
- optionally persists polygons via `spatialDb.ts`

This file is critical whenever rendering issues appear.

## 8. Feature Maturity Map

### Strongest areas

- DGGS-backed viewport rendering
- dataset lookup flow
- persistent spatial ops in `ops_service.py`
- topology-backed traversal
- upload pipeline
- STAC discovery/index/ingest foundation

### Present but lighter-weight

- enhanced zonal stats and spatial analysis
- collaborative annotations
- temporal operations
- cellular automata
- prediction/ML workflows

### Legacy or overlapping areas

- `toolbox.py` overlaps with `ops.py`
- `/workbench` overlaps with `/dashboard`
- top-level docs describe different generations of the system

## 9. Known Drift And Fragile Areas

These are important context points before making changes.

### Schema drift

`backend/db/schema.sql` does not fully match the ORM models and migrations.

Examples:

- `User` model includes `role` and `is_active`, but `schema.sql` does not.
- `Dataset` model includes `visibility` and `shared_with`, but `schema.sql` does not.
- annotation ORM models differ materially from the Alembic migration schema.

Practical consequence:

- startup via `schema.sql` and development via ORM/migrations are not guaranteed to produce the same database shape

### Migration story is incomplete

Alembic files exist under `backend/backend/migrations/`, but normal app startup does not use them.

### Frontend API-shape mismatch

`fetchDatasets()` returns the full `/api/datasets` payload, while several consumers of `useDatasets()` treat `data` like a plain dataset array.

Affected call sites include:

- `DatasetSearch.tsx`
- `Workbench.tsx`
- `OperationResultsList.tsx`

This is a likely source of UI breakage or hidden assumptions.

### Tests and runtime assumptions drift

The tests mix three modes:

- in-process ASGI tests
- direct database integration tests
- live-server tests against `http://localhost:4000`

There are also stale assumptions, for example tests that expect auth on routes whose current implementation is public.

### Docs drift

`README.md`, `ANALYSIS.md`, `IMPLEMENTATION_SUMMARY.md`, and `CLAUDE.md` describe overlapping but not identical system states.

Use the code as source of truth.

## 10. Where To Change Things

### If the task is about map rendering

Start in:

- `frontend/src/components/MapView.tsx`
- `frontend/src/lib/dggal.ts`
- `backend/app/routers/topology.py`
- `backend/app/dggal_utils.py`

### If the task is about spatial operations

Start in:

- `frontend/src/components/ToolboxPanel.tsx`
- `frontend/src/lib/toolRegistry.ts`
- `backend/app/routers/ops.py`
- `backend/app/services/ops_service.py`
- `backend/app/services/spatial_engine.py`

### If the task is about ingestion

Start in:

- `backend/app/routers/uploads.py`
- `backend/app/services/ingest.py`
- `backend/app/services/vector_ingest.py`
- `backend/app/services/raster_ingest.py`
- `backend/app/celery_app.py`

### If the task is about STAC

Start in:

- `frontend/src/components/StacBrowser.tsx`
- `backend/app/routers/stac.py`
- `backend/app/services/stac_discovery.py`
- `backend/app/services/stac_indexer.py`
- `backend/app/services/stac_ingest.py`

### If the task is about auth or permissions

Start in:

- `backend/app/auth.py`
- `backend/app/authorization.py`
- `backend/app/routers/auth.py`
- `backend/app/models.py`

## 11. Practical Guidance For Future Work

Before making feature changes, first decide which of these layers is authoritative:

- raw `schema.sql`
- Alembic migration files
- SQLAlchemy ORM models

Right now they are not fully synchronized.

Before making frontend data-flow changes, verify API response shapes directly in:

- `frontend/src/lib/api.ts`
- router return payloads in `backend/app/routers/`

Before using advanced modules in product work, verify whether the service is real or simulated. This matters especially for:

- `prediction.py`
- parts of `temporal.py`
- parts of the collaboration stack

## 12. Short Summary

The codebase has a real DGGS application core with a clear architecture:

- PostgreSQL stores DGGS cell facts
- topology is precomputed
- FastAPI exposes dataset and analysis APIs
- React renders DGGS geometry client-side through DGGAL

The main caution is not conceptual complexity. It is drift:

- schema vs model drift
- docs vs code drift
- some UI/API shape drift
- a few newer modules that are more scaffold than product-hardened

That context should frame all future debugging and implementation work in this repository.
