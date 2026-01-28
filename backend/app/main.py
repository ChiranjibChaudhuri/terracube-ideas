from contextlib import asynccontextmanager, suppress
import asyncio
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CORS_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import auth, topology, datasets, uploads, analytics, toolbox, stats, ops

# ...

app.include_router(auth.router)
app.include_router(topology.router)
app.include_router(ops.router)
app.include_router(datasets.router)
app.include_router(uploads.router)
app.include_router(analytics.router)
app.include_router(toolbox.router)
app.include_router(stats.router)

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
