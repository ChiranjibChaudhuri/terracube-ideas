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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await seed_admin()

    cleanup_task = asyncio.create_task(
        run_result_cleanup_loop(settings.RESULT_TTL_HOURS, settings.RESULT_CLEANUP_INTERVAL_MINUTES)
    )
    
    # Data loading moved to external 'data-init' service
    # See app/scripts/init_data.py
        
    yield
    # Shutdown (close DB pool if needed, handled globally but good practice)
    cleanup_task.cancel()
    with suppress(asyncio.CancelledError):
        await cleanup_task
    from app.db import close_db_pool
    await close_db_pool()

app = FastAPI(title="TerraCube IDEAS API", lifespan=lifespan)

# Rate limiting
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later.", "retry_after": 60}
    )

@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors with user-friendly messages."""
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"] if loc != "body")
        message = error["msg"]
        errors.append({
            "field": field,
            "message": message
        })
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation failed", "errors": errors}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent error response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions gracefully."""
    import traceback as tb
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

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
        "/assets"
    ]
)

from app.routers import auth, topology, datasets, uploads, analytics, toolbox, stats, ops, upload_status

# ...

app.include_router(auth.router)
app.include_router(topology.router)
app.include_router(ops.router)
app.include_router(datasets.router)
app.include_router(uploads.router)
app.include_router(analytics.router)
app.include_router(toolbox.router)
app.include_router(stats.router)
app.include_router(upload_status.router)

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)

@app.get("/api/health")
async def health_check():
    from app.db import AsyncSessionLocal
    from sqlalchemy import text
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e)})

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
