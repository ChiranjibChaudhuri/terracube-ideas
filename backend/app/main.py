from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.init_db import init_db
from app.seed import seed_admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await seed_admin()
    
    # Load real global data from Natural Earth (optional)
    if settings.LOAD_REAL_DATA:
        logger = logging.getLogger("uvicorn.error")
        from app.db import AsyncSessionLocal
        from app.services.real_data_loader import load_real_global_data
        from app.services.data_loader import load_initial_data
        try:
            async with AsyncSessionLocal() as session:
                await load_real_global_data(session)
                await load_initial_data(session)  # Also load demo raster datasets
        except Exception as exc:
            logger.warning(f"Skipping data load: {exc}")
        
    yield
    # Shutdown (close DB pool if needed, handled globally but good practice)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
