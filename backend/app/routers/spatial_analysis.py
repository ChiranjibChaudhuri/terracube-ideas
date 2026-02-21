"""
Spatial Analysis Router - Advanced DGGS Spatial Analysis Endpoints

Exposes the following algorithms:
- Moran's I (Global Spatial Autocorrelation)
- LISA (Local Indicators of Spatial Association)
- DBSCAN Clustering
- Kernel Density Estimation
- Change Detection
- Flow Direction / Watershed
- Shortest Path
- Contour / Isoline (via ops)
- IDW Interpolation (via ops)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from app.db import get_db
from app.services.spatial_analysis import get_spatial_analysis_service
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["Spatial Analysis"])


# --- Request/Response Models ---

class MoransIRequest(BaseModel):
    dataset_id: str
    variable: str
    weight_type: str = "binary"

class LISARequest(BaseModel):
    dataset_id: str
    variable: str
    limit: int = Field(default=5000, ge=1, le=50000)

class DBSCANRequest(BaseModel):
    dataset_id: str
    variable: str
    eps_rings: int = Field(default=2, ge=1, le=10)
    min_pts: int = Field(default=3, ge=1, le=50)
    value_threshold: float = Field(default=0.5, ge=0, le=10)
    limit: int = Field(default=5000, ge=1, le=50000)

class ChangeDetectionRequest(BaseModel):
    dataset_a_id: str
    dataset_b_id: str
    variable: str
    threshold: float = Field(default=0.0, ge=0)
    limit: int = Field(default=10000, ge=1, le=50000)

class FlowDirectionRequest(BaseModel):
    dataset_id: str
    elevation_attr: str = "elevation"

class ShortestPathRequest(BaseModel):
    start_dggid: str
    end_dggid: str
    cost_dataset_id: Optional[str] = None
    cost_attr: str = "cost"
    max_hops: int = Field(default=100, ge=1, le=500)

class KernelDensityRequest(BaseModel):
    dataset_id: str
    variable: str
    bandwidth: int = Field(default=3, ge=1, le=10)
    kernel: str = Field(default="gaussian", pattern="^(gaussian|linear|uniform)$")

class FlowAccumulationRequest(BaseModel):
    dataset_id: str
    elevation_attr: str = "elevation"

class ViewshedRequest(BaseModel):
    dataset_id: str
    observer_dggid: str
    elevation_attr: str = "elevation"
    observer_height: float = Field(default=1.8, ge=0, le=1000)
    max_radius: int = Field(default=20, ge=1, le=50)

class VoronoiRequest(BaseModel):
    dataset_id: str
    seed_attr: str = "category"
    max_radius: int = Field(default=50, ge=1, le=100)


# --- Endpoints ---

@router.post("/morans-i")
async def compute_morans_i(
    req: MoransIRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Compute Global Moran's I spatial autocorrelation.

    Measures whether a variable exhibits spatial clustering (+1),
    random distribution (0), or dispersion (-1).
    """
    try:
        service = get_spatial_analysis_service(db)
        result = await service.morans_i(req.dataset_id, req.variable, req.weight_type)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Moran's I failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lisa")
async def compute_lisa(
    req: LISARequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Compute Local Indicators of Spatial Association (LISA).

    Identifies local clusters and outliers:
    - HH: High-High clusters (hotspots)
    - LL: Low-Low clusters (coldspots)
    - HL: High-Low outliers
    - LH: Low-High outliers
    """
    try:
        service = get_spatial_analysis_service(db)
        result = await service.lisa(req.dataset_id, req.variable, req.limit)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"LISA failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dbscan")
async def compute_dbscan(
    req: DBSCANRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    DBSCAN spatial clustering on DGGS grid.

    Groups cells into clusters based on spatial proximity and value similarity.
    Does not require specifying number of clusters upfront.
    """
    try:
        service = get_spatial_analysis_service(db)
        result = await service.dbscan_cluster(
            req.dataset_id, req.variable,
            req.eps_rings, req.min_pts, req.value_threshold, req.limit
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"DBSCAN failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/change-detection")
async def compute_change_detection(
    req: ChangeDetectionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Multi-temporal change detection between two datasets.

    Classifies each cell's change as: gain, loss, stable, appeared, or disappeared.
    Returns absolute and percentage changes.
    """
    try:
        service = get_spatial_analysis_service(db)
        result = await service.change_detection(
            req.dataset_a_id, req.dataset_b_id,
            req.variable, req.threshold, req.limit
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Change detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flow-direction")
async def compute_flow_direction(
    req: FlowDirectionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Compute flow direction and accumulation from elevation data.

    For each cell, finds steepest descent neighbor. Creates a new dataset
    with flow direction vectors and accumulation counts.
    """
    try:
        service = get_spatial_analysis_service(db)
        result = await service.flow_direction(req.dataset_id, req.elevation_attr)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Flow direction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shortest-path")
async def compute_shortest_path(
    req: ShortestPathRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Find shortest path between two DGGS cells.

    Uses BFS (unweighted) or Dijkstra (with cost dataset) on the topology graph.
    Returns the path as an ordered list of DGGIDs.
    """
    try:
        service = get_spatial_analysis_service(db)
        result = await service.shortest_path(
            req.start_dggid, req.end_dggid,
            req.cost_dataset_id, req.cost_attr, req.max_hops
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Shortest path failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kernel-density")
async def compute_kernel_density(
    req: KernelDensityRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Kernel Density Estimation on DGGS grid.

    Creates a smooth density surface by spreading values using a kernel function.
    Supports Gaussian, linear, and uniform kernels.
    """
    try:
        service = get_spatial_analysis_service(db)
        result = await service.kernel_density(
            req.dataset_id, req.variable,
            req.bandwidth, req.kernel
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Kernel density failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flow-accumulation")
async def compute_flow_accumulation(
    req: FlowAccumulationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Compute flow accumulation (watershed delineation) from elevation.

    Counts how many upstream cells drain through each cell.
    High values indicate rivers/valleys.
    """
    try:
        service = get_spatial_analysis_service(db)
        result = await service.flow_accumulation(req.dataset_id, req.elevation_attr)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Flow accumulation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/viewshed")
async def compute_viewshed(
    req: ViewshedRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Viewshed analysis from an observer cell.

    Determines which cells are visible from the observer using elevation data.
    Returns a new dataset with visibility values (1=visible, 0=hidden).
    """
    try:
        service = get_spatial_analysis_service(db)
        result = await service.viewshed(
            req.dataset_id, req.observer_dggid,
            req.elevation_attr, req.observer_height, req.max_radius
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Viewshed failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voronoi")
async def compute_voronoi_zones(
    req: VoronoiRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Voronoi / Proximity Zones on DGGS grid.

    Assigns every reachable cell to its nearest seed cell using BFS expansion.
    Creates natural Thiessen polygons on the hexagonal grid.
    """
    try:
        service = get_spatial_analysis_service(db)
        result = await service.voronoi_zones(req.dataset_id, req.seed_attr, req.max_radius)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Voronoi zones failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities")
async def get_analysis_capabilities():
    """List all available spatial analysis algorithms and their parameters."""
    return {
        "algorithms": [
            {
                "name": "morans_i",
                "endpoint": "/api/analysis/morans-i",
                "description": "Global Moran's I spatial autocorrelation",
                "category": "autocorrelation",
                "inputs": ["dataset_id", "variable"],
                "outputs": ["morans_i", "z_score", "significance", "interpretation"]
            },
            {
                "name": "lisa",
                "endpoint": "/api/analysis/lisa",
                "description": "Local Indicators of Spatial Association (Local Moran's I)",
                "category": "autocorrelation",
                "inputs": ["dataset_id", "variable"],
                "outputs": ["cells with cluster_type (HH/LL/HL/LH/NS)"]
            },
            {
                "name": "dbscan",
                "endpoint": "/api/analysis/dbscan",
                "description": "DBSCAN spatial clustering",
                "category": "clustering",
                "inputs": ["dataset_id", "variable", "eps_rings", "min_pts"],
                "outputs": ["clusters with cell lists and statistics"]
            },
            {
                "name": "change_detection",
                "endpoint": "/api/analysis/change-detection",
                "description": "Multi-temporal change detection",
                "category": "temporal",
                "inputs": ["dataset_a_id", "dataset_b_id", "variable", "threshold"],
                "outputs": ["cells with change_type and magnitude"]
            },
            {
                "name": "flow_direction",
                "endpoint": "/api/analysis/flow-direction",
                "description": "Flow direction and accumulation from elevation",
                "category": "hydrology",
                "inputs": ["dataset_id", "elevation_attr"],
                "outputs": ["result dataset with flow vectors"]
            },
            {
                "name": "shortest_path",
                "endpoint": "/api/analysis/shortest-path",
                "description": "Shortest path between two DGGS cells",
                "category": "network",
                "inputs": ["start_dggid", "end_dggid", "cost_dataset_id"],
                "outputs": ["path", "total_cost", "hops"]
            },
            {
                "name": "kernel_density",
                "endpoint": "/api/analysis/kernel-density",
                "description": "Kernel Density Estimation",
                "category": "density",
                "inputs": ["dataset_id", "variable", "bandwidth", "kernel"],
                "outputs": ["result dataset with density surface"]
            },
            {
                "name": "hotspots",
                "endpoint": "/api/stats/enhanced/hotspots",
                "description": "Getis-Ord Gi* hotspot analysis",
                "category": "autocorrelation",
                "inputs": ["dataset_id", "variable", "radius"],
                "outputs": ["cells with gi_z_score and significance"]
            },
            {
                "name": "contour",
                "endpoint": "/api/ops (op_type=contour)",
                "description": "Contour/isoline detection",
                "category": "spatial",
                "inputs": ["dataset_a_id", "num_levels"],
                "outputs": ["result dataset with contour lines"]
            },
            {
                "name": "idw_interpolation",
                "endpoint": "/api/ops (op_type=idw_interpolation)",
                "description": "Inverse Distance Weighting interpolation",
                "category": "interpolation",
                "inputs": ["dataset_a_id", "radius"],
                "outputs": ["result dataset with interpolated values"]
            },
            {
                "name": "symmetric_difference",
                "endpoint": "/api/ops (op_type=symmetric_difference)",
                "description": "Cells in A XOR B",
                "category": "spatial",
                "inputs": ["dataset_a_id", "dataset_b_id"],
                "outputs": ["result dataset"]
            },
            {
                "name": "buffer_weighted",
                "endpoint": "/api/ops (op_type=buffer_weighted)",
                "description": "Distance-weighted buffer with decay",
                "category": "spatial",
                "inputs": ["dataset_a_id", "iterations"],
                "outputs": ["result dataset with distance values"]
            },
            {
                "name": "flow_accumulation",
                "endpoint": "/api/analysis/flow-accumulation",
                "description": "Watershed delineation and flow accumulation",
                "category": "hydrology",
                "inputs": ["dataset_id", "elevation_attr"],
                "outputs": ["result dataset with accumulation counts"]
            },
            {
                "name": "viewshed",
                "endpoint": "/api/analysis/viewshed",
                "description": "Line-of-sight visibility analysis",
                "category": "terrain",
                "inputs": ["dataset_id", "observer_dggid", "elevation_attr", "max_radius"],
                "outputs": ["result dataset with visibility (1/0)"]
            },
            {
                "name": "voronoi_zones",
                "endpoint": "/api/analysis/voronoi",
                "description": "Voronoi / proximity zones (Thiessen polygons)",
                "category": "spatial",
                "inputs": ["dataset_id", "seed_attr", "max_radius"],
                "outputs": ["result dataset with zone assignments and distances"]
            }
        ]
    }
