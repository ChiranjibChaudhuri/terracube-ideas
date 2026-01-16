from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import auth
from app.init_db import init_db
from app.seed import seed_admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await seed_admin()
    
    # Load demo data
    from app.db import AsyncSessionLocal
    from app.services.data_loader import load_initial_data
    async with AsyncSessionLocal() as session:
        await load_initial_data(session)
        
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
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
