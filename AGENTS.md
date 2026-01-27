# Repository Guidelines

## Project Structure & Module Organization
- `backend/`: FastAPI API + Celery worker. Core routes live in `backend/app/routers`, worker config in `backend/app/celery_app.py`, and SQL schema/sample data in `backend/db/`.
- `frontend/`: Vite + React UI. Pages are in `frontend/src/pages`, shared UI in `frontend/src/components`, and client DGGS helpers in `frontend/src/lib`.
- `frontend/public/dggal`: DGGAL WASM assets used for client-side geometry generation.
- `public/`: shared brand assets (logo, favicon, images).
- `Reading_Material/`: reference docs for DGGAL + IDEAS.
- `docker-compose.yml`: local Postgres, Redis, MinIO.

## Build, Test, and Development Commands
- `docker compose up -d`: start Postgres/Redis/MinIO.
- `psql postgresql://ideas_user:ideas_password@localhost:5433/ideas -f backend/db/schema.sql`: create tables.
- `cd backend && cp .env.example .env && python -m venv .venv && source .venv/bin/activate && pip install -e .`: backend setup.
- `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 4000`: start API server.
- `cd backend && source .venv/bin/activate && celery -A app.celery_app worker --loglevel=info`: start preprocessing worker.
- `cd frontend && npm install && npm run dev`: start UI dev server.
- `cd frontend && npm run build && npm run preview`: build + preview UI.

## Coding Style & Naming Conventions
- Python for the backend and TypeScript (ESM) for the frontend; use 4‑space indentation in Python and 2‑space indentation + semicolons in TS.
- Use `PascalCase` for React components and their files (e.g., `LandingPage.tsx`), `camelCase` for functions/variables.
- No formatter or linter configured; match existing style in touched files.

## Testing Guidelines
- **Backend**: Uses `pytest` with `pytest-asyncio` for async DB tests.
  - Run tests: `pytest backend/tests`
  - Integration tests: `test_toolbox_integration.py` (API flows), `test_spatial_ops_db.py` (DB persistence), `test_multi_res_loader.py` (Data loading).
- **Frontend**: Uses `vitest` with `@testing-library/react` and `jsdom`.
  - Run tests: `cd frontend && npm test`
  - Unit tests: located in `frontend/src/__tests__/` (e.g. `MapView.test.tsx`).
- **Docker**: `docker-compose build` is verified working for containerization.

## Commit & Pull Request Guidelines
- No git history is present, so no established commit convention. Prefer short, imperative messages (e.g., “Add viewport DGGS lookup endpoint”).
- PRs should include: summary, run/verify steps, and screenshots for UI changes. Call out any schema or environment changes.

## Configuration & Secrets
- Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env`.
- Never commit real secrets; update `.env.example` when new config is required.
