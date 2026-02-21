from contextlib import asynccontextmanager, suppress
import asyncio
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from slowapi import Limiter, _rate_limit_exceeded
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.init_db import init_db
from app.seed import seed_admin
from app.services.result_cleanup import run_result_cleanup_loop
from app.exceptions import setup_global_handlers, RequestIdMiddleware, validate_settings
from app.logging_config import setup_logging, RequestLoggingMiddleware, log_performance

logger = logging.getLogger(__name__)

# Set up structured logging
setup_logging()

logger = logging.getLogger(__name__)


async def validate_settings():
    """
    Validate required settings at startup.
    Fail fast if critical configuration is missing.
    """
    errors = []

    # Check database URL
    if not settings.DATABASE_URL or "postgresql://" not in settings.DATABASE_URL:
        errors.append("DATABASE_URL must be set to a valid PostgreSQL connection string")

    # Check JWT secret
    if not settings.JWT_SECRET or len(settings.JWT_SECRET) < 32:
        errors.append("JWT_SECRET must be set and at least 32 characters")

    # Check CORS origin in production
    if settings.CORS_ORIGIN == "*":
        logger.warning("CORS_ORIGIN is set to wildcard (*) - this is insecure for production")

    # Check MinIO settings
    if not settings.MINIO_ENDPOINT or not settings.MINIO_PORT:
        errors.append("MinIO settings (MINIO_ENDPOINT, MINIO_PORT) must be configured")

    # Check upload directory
    upload_dir = Path(settings.UPLOAD_DIR)
    if not upload_dir.exists():
        try:
            upload_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created upload directory: {upload_dir}")
        except Exception as e:
            errors.append(f"Cannot create upload directory: {e}")

    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.critical(error_msg)
        raise RuntimeError(error_msg)

    logger.info("Configuration validation passed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting TerraCube IDEAS API...")
    # Store settings in app state for access in exception handlers
    app.state.settings = settings
    await validate_settings()
    await init_db()
    await seed_admin()

    # Start result cleanup task
    cleanup_task = asyncio.create_task(
        run_result_cleanup_loop(settings.RESULT_TTL_HOURS, settings.RESULT_CLEANUP_INTERVAL_MINUTES)
    )

    # Data loading moved to external 'data-init' service
    # See app/scripts/init_data.py

    logger.info("Startup complete. Server ready.")

    yield

    # Shutdown
    logger.info("Shutting down...")
    cleanup_task.cancel()
    with suppress(asyncio.CancelledError):
        await cleanup_task
    from app.db import close_db_pool
    await close_db_pool()

app = FastAPI(title="TerraCube IDEAS API", lifespan=lifespan)

# Setup global exception handlers before other middleware
setup_global_handlers(app)

# Add request ID middleware for tracing
app.add_middleware(RequestIdMiddleware)

# Add request logging middleware (configured via ENVIRONMENT)
request_logger = RequestLoggingMiddleware(app, enabled=settings.ENVIRONMENT != "development")
app.add_middleware(request_logger)

# Rate limiting (updated to use per-user limiting)
from app.rate_limiter import get_per_user_limiter
limiter = get_per_user_limiter()
app.state.limiter = limiter

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CORS_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Apply rate limiting to all routes
app.add_middleware(
    limiter,
    exempt_routes=[
        "/api/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/dggal",
        "/assets",
        "/api/auth/login",  # Allow login
        "/api/auth/register"  # Allow registration
    ]
)

from app.routers import (
    auth, topology, datasets, uploads, analytics, toolbox,
    stats, ops, upload_status,
    stats_enhanced,  # Enhanced zonal statistics
    annotations,       # Collaborative annotations
    prediction,        # ML predictions and fire spread
    temporal,          # Temporal operations and CA
    ogc,               # OGC API Features
    spatial_analysis   # Advanced spatial analysis algorithms
)

# Register API routes
app.include_router(auth.router)
app.include_router(topology.router)
app.include_router(ops.router)
app.include_router(datasets.router)
app.include_router(uploads.router)
app.include_router(analytics.router)
app.include_router(toolbox.router)
app.include_router(stats.router)
app.include_router(upload_status.router)
# New feature routers
app.include_router(stats_enhanced.router)
app.include_router(annotations.router)
app.include_router(prediction.router)
app.include_router(temporal.router)
app.include_router(ogc.router)
app.include_router(spatial_analysis.router)

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)

@app.get("/api/health")
async def health_check():
    """
    Basic health check endpoint.
    Returns status of database and topology population.
    """
    from app.db import AsyncSessionLocal
    from sqlalchemy import select, text

    try:
        async with AsyncSessionLocal() as session:
            # Check database connection
            await session.execute(text("SELECT 1"))

            # Check topology population
            topo_result = await session.fetchrow("SELECT COUNT(*) FROM dgg_topology")
            topo_count = topo_result[0] if topo_result else 0
            is_populated = topo_count > 0

            # Get data counts
            ds_count = await session.fetchrow("SELECT COUNT(*) FROM datasets")
            cell_count = await session.fetchrow("SELECT COUNT(*) FROM cell_objects")

            return JSONResponse({
                "status": "ok",
                "database": "connected",
                "topology_populated": is_populated,
                "topology_rows": topo_count,
                "datasets": ds_count[0] if ds_count else 0,
                "cells": cell_count[0] if cell_count else 0
            })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.get("/api/health/db")
async def database_health():
    """
    Detailed database health check.
    Returns connection pool metrics and database status.
    """
    from app.db import get_db_health

    health = await get_db_health()

    status_code = 200 if health["status"] == "healthy" else 503
    return JSONResponse(
        status_code=status_code,
        content=health
    )

# Serve Frontend
# Determine path to frontend/dist relative to this file
# app/main.py -> app -> backend -> repo root -> frontend/dist
BASE_DIR = Path(__file__).resolve().parent.parent.parent
frontend_dist = BASE_DIR / "frontend" / "dist"

if frontend_dist.exists():
    # Mount assets and dggal directories for efficiency
    if (frontend_dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    if (frontend_dist / "dggal").exists():
        app.mount("/dggal", StaticFiles(directory=frontend_dist / "dggal"), name="dggal")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Allow API calls to pass through (and fail with 404 if not found)
        # Also exclude metrics or docs if needed, but docs is /docs by default
        if full_path.startswith("api") or full_path.startswith("metrics") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            raise HTTPException(status_code=404, detail="Not Found")

        # Check if a static file exists (e.g. favicon.svg, logo.svg)
        file_path = frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(file_path)

        # Fallback to index.html for SPA routing
        return FileResponse(frontend_dist / "index.html")
else:
    logger.warning(f"Frontend dist not found at {frontend_dist}, API only mode")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
