# TerraCube IDEAS Engine Analysis

## Executive Summary

Deep analysis of all backend algorithms, services, and spatial operations in TerraCube IDEAS. This document catalogs what the engine **can do**, what's **broken**, and what **new capabilities** can be added.

---

## 1. Current Algorithm Inventory

### 1.1 Spatial Operations (Working)

| Operation | Location | Method | Status |
|-----------|----------|--------|--------|
| Intersection | `ops_service.py:245` | SQL INNER JOIN on dggid/tid/attr_key | Working (with caveats) |
| Union | `ops_service.py:265` | INSERT A + INSERT B WHERE NOT EXISTS | **BUG** in line 285 |
| Difference | `ops_service.py:290` | LEFT JOIN + IS NULL filter | Working |
| Buffer (K-ring) | `ops_service.py:301` | Recursive CTE on dgg_topology | Working (requires topology) |
| Aggregate | `ops_service.py:318` | JOIN topology + GROUP BY parent | Working (AVG only) |
| Propagate | `ops_service.py:331` | Recursive CTE + mask constraint | Working |

### 1.2 Client-Side Operations (Working)

| Operation | Location | Method |
|-----------|----------|--------|
| Buffer | `spatial_engine.py:29` | Async DGGAL neighbor iteration |
| Aggregate | `spatial_engine.py:57` | Async DGGAL parent traversal |
| Expand (Refine) | `spatial_engine.py:74` | Async DGGAL children traversal |
| Set Ops | `spatial_engine.py:98` | Python set operations |

### 1.3 Statistics (Partially Working)

| Operation | Location | Status |
|-----------|----------|--------|
| Sum/Mean/Min/Max/Count | `zonal_stats.py:150-224` | Working |
| Median (percentile) | `zonal_stats.py:170` | Working |
| StdDev/Variance | `zonal_stats.py:198-215` | Working |
| Mode | `zonal_stats.py:227` | **BUG** - accesses wrong column |
| Percentiles | `zonal_stats.py:236` | Working |
| Histogram | `zonal_stats.py:246` | Working |
| Correlation | `zonal_stats.py:306` | **BUG** - wrong formula |
| Hotspot (Gi*) | `zonal_stats.py:371` | **BUG** - SQL errors |

### 1.4 Temporal (Partially Working)

| Operation | Location | Status |
|-----------|----------|--------|
| Hierarchy | `temporal.py:71` | Working (metadata only) |
| Snapshot | `temporal.py:105` | **STUB** - returns metadata, no data |
| Range | `temporal.py:150` | Working |
| Aggregate | `temporal.py:230` | **BUG** - `:agg_func` can't be SQL-bound |
| Difference | `temporal.py:308` | Working (numeric only) |
| Time Series | `temporal.py:364` | Working |

### 1.5 Cellular Automata (Partially Working)

| Operation | Location | Status |
|-----------|----------|--------|
| Initialize | `temporal.py:445` | Config only, rules unused |
| CA Step | `temporal.py:487` | Basic neighbor spread, ignores all rules |
| CA Run | `temporal.py:558` | Loops ca_step, no statistics |

### 1.6 Prediction/ML (Not Working)

| Operation | Location | Status |
|-----------|----------|--------|
| Training | `prediction.py:133` | **SIMULATED** - returns fake metrics |
| Prediction | `prediction.py:226` | **SIMULATED** - returns fake dataset ID |
| Fire Spread | `prediction.py:348` | **SIMULATED** - hardcoded results |
| Fire Risk Map | `prediction.py:394` | **SIMULATED** - hardcoded percentages |

### 1.7 Data Cube (Partially Working)

| Operation | Location | Status |
|-----------|----------|--------|
| Aggregated Dataset | `datacube.py:35` | Working (requires topology) |
| Resolution Pyramid | `datacube.py:255` | Working |
| Materialized Views | `datacube.py:303` | Created but never used |

---

## 2. Critical Bugs Found

### Bug 1: Union operation has broken COALESCE logic
**File:** `ops_service.py:285`
```sql
AND COALESCE(a.tid, b.tid)  -- This is NOT a comparison!
```
**Fix:** Should be `AND a.tid = b.tid`

### Bug 2: Correlation uses wrong formula
**File:** `zonal_stats.py:347`
```sql
AVG(val_a * val_b)  -- This is NOT Pearson correlation
```
**Fix:** Should use `CORR(val_a, val_b)` (PostgreSQL built-in) or the full Pearson formula.

### Bug 3: Correlation SQL has invalid GROUP BY
**File:** `zonal_stats.py:350`
```sql
GROUP BY a.dggid, b.dggid  -- References aliases from CTE, not outer query
```
The entire correlation query structure is broken and won't execute.

### Bug 4: Temporal aggregate can't bind function name
**File:** `temporal.py:285`
```sql
:agg_func(value_num)  -- Parameter binding doesn't work for SQL functions
```
**Fix:** Use conditional SQL string construction or a mapping approach.

### Bug 5: Hotspot analysis has multiple SQL issues
**File:** `zonal_stats.py:400-438`
- `cell_stats` CTE computes global stats but then tries to join per-cell
- GROUP BY is missing in the `neighbors` CTE
- `base_level` parameter used incorrectly (level means resolution, not ring distance)

### Bug 6: Topology check doesn't actually prevent empty results
**File:** `ops_service.py:158-164`
```python
topology_check = await self.db.execute(text("SELECT 1 FROM dgg_topology LIMIT 1"))
if topology_check.scalar() == 0:  # SELECT 1 returns 1, not 0!
```
**Fix:** Check for `is None` instead of `== 0`.

---

## 3. Enhancement Opportunities for Existing Algorithms

### 3.1 Spatial Operations Enhancements

#### A. Weighted Intersection
Currently averages values `(a + b) / 2`. Should support configurable merge strategies:
- **Weighted average** with user-defined weights
- **Priority merge** (keep A or B value)
- **Max/Min** selection
- **Custom expression** (e.g., `a.value * 0.7 + b.value * 0.3`)

#### B. Multi-Aggregation Methods for Aggregate
Currently hardcoded to `AVG()`. Should support:
- `SUM`, `MIN`, `MAX`, `COUNT`, `STDDEV`
- **Weighted average** by cell area contribution
- **Mode** for categorical data
- User-selectable method per operation

#### C. Distance-Weighted Buffer
Current buffer treats all K-ring cells equally. Enhancement:
- Assign distance value (depth) to each buffered cell
- Support distance decay functions: linear, exponential, Gaussian
- Enable "influence zone" modeling (e.g., pollution dispersion)

#### D. Symmetric Difference
Missing operation: cells in A XOR B (in one but not both).
```sql
-- Cells in A but not B + Cells in B but not A
```

#### E. Multi-Resolution Operations
Currently all ops require matching resolution. Enhancement:
- Auto-refine coarser dataset to match finer before operation
- Auto-aggregate finer dataset to match coarser
- User chooses target resolution

---

### 3.2 Statistics Enhancements

#### A. Proper Pearson Correlation
Replace broken implementation with PostgreSQL's built-in `CORR()`:
```sql
SELECT CORR(a.value_num, b.value_num) FROM ...
```

#### B. Spatial Autocorrelation (Moran's I)
Measures degree of spatial clustering:
```
I = (N / W) * (Σᵢ Σⱼ wᵢⱼ(xᵢ - x̄)(xⱼ - x̄)) / (Σᵢ(xᵢ - x̄)²)
```
Uses topology table for neighbor weights. Critical for understanding spatial patterns.

#### C. Geary's C
Complementary to Moran's I, measures local spatial autocorrelation:
```
C = ((N-1) / 2W) * (Σᵢ Σⱼ wᵢⱼ(xᵢ - xⱼ)²) / (Σᵢ(xᵢ - x̄)²)
```

#### D. Local Indicators of Spatial Association (LISA)
Per-cell version of Moran's I - identifies local clusters and outliers:
- High-High clusters (hotspots)
- Low-Low clusters (coldspots)
- High-Low outliers
- Low-High outliers

#### E. Spatial Regression
Use spatial weights from topology for spatial lag / spatial error models.

---

### 3.3 Temporal Enhancements

#### A. Moving Average / Rolling Window
Compute rolling statistics across temporal dimension:
```sql
AVG(value_num) OVER (PARTITION BY dggid ORDER BY tid ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING)
```

#### B. Trend Detection
Compute linear trend per cell across time:
- Slope (rate of change)
- R² (fit quality)
- Mann-Kendall test (non-parametric trend)

#### C. Anomaly Detection
Flag cells where value deviates significantly from:
- Temporal baseline (historical mean ± N*stddev)
- Spatial neighborhood (Local Outlier Factor)
- Combined spatiotemporal anomaly

#### D. Seasonal Decomposition
Separate time series into: trend + seasonal + residual components.

---

## 4. New Algorithm Categories to Add

### 4.1 Spatial Interpolation (Kriging on DGGS)

**Purpose:** Estimate values at unmeasured cells using measured neighbors.

**Implementation approach:**
1. Build spatial weight matrix from `dgg_topology`
2. Compute semi-variogram from measured cell pairs
3. Use ordinary kriging to predict missing cell values
4. Store predictions as new dataset

**SQL-friendly approach (Inverse Distance Weighting):**
```sql
WITH measured AS (
    SELECT dggid, value_num FROM cell_objects WHERE dataset_id = :ds AND attr_key = :key
),
predictions AS (
    SELECT t.neighbor_dggid AS target,
           SUM(m.value_num / (depth + 1.0)) / SUM(1.0 / (depth + 1.0)) AS predicted
    FROM measured m
    JOIN dgg_topology_kring(m.dggid, :radius) t ON TRUE
    WHERE NOT EXISTS (SELECT 1 FROM measured m2 WHERE m2.dggid = t.neighbor_dggid)
    GROUP BY t.neighbor_dggid
)
INSERT INTO cell_objects ...
```

### 4.2 Watershed / Flow Accumulation on DGGS

**Purpose:** Model water flow across the hexagonal grid using elevation data.

**Implementation:**
1. For each cell, find lowest neighbor (steepest descent)
2. Build flow direction graph
3. Accumulate flow from uphill cells
4. Identify watersheds (connected drainage basins)

```sql
-- Flow direction: find lowest neighbor for each cell
WITH flow_dir AS (
    SELECT a.dggid AS source,
           b.dggid AS target,
           ROW_NUMBER() OVER (PARTITION BY a.dggid ORDER BY b.value_num ASC) AS rn
    FROM cell_objects a
    JOIN dgg_topology t ON a.dggid = t.dggid
    JOIN cell_objects b ON t.neighbor_dggid = b.dggid
        AND b.dataset_id = a.dataset_id AND b.attr_key = 'elevation'
    WHERE a.dataset_id = :ds AND a.attr_key = 'elevation'
        AND b.value_num < a.value_num  -- downhill only
)
SELECT source, target FROM flow_dir WHERE rn = 1
```

### 4.3 Viewshed Analysis on DGGS

**Purpose:** Determine which cells are visible from an observer cell.

**Implementation:**
1. From observer cell, cast rays in all 6 hex directions
2. Track max elevation angle along each ray
3. Cell is visible if its elevation angle exceeds max so far
4. Uses topology table for directional traversal

### 4.4 Shortest Path / Network Analysis

**Purpose:** Find shortest path between two DGGS cells, optionally weighted by terrain.

**Implementation using Dijkstra on topology:**
```sql
WITH RECURSIVE path AS (
    SELECT dggid, 0 AS cost, ARRAY[dggid] AS route
    FROM (VALUES (:start_cell)) AS s(dggid)
    UNION ALL
    SELECT t.neighbor_dggid,
           p.cost + COALESCE(c.value_num, 1.0),  -- weight by attribute
           p.route || t.neighbor_dggid
    FROM path p
    JOIN dgg_topology t ON p.dggid = t.dggid
    LEFT JOIN cell_objects c ON t.neighbor_dggid = c.dggid
        AND c.dataset_id = :cost_ds AND c.attr_key = :cost_attr
    WHERE t.neighbor_dggid != ALL(p.route)  -- prevent cycles
        AND p.cost < :max_cost
)
SELECT * FROM path WHERE dggid = :end_cell ORDER BY cost LIMIT 1
```

### 4.5 Contour / Isoline Generation

**Purpose:** Generate isolines (equal-value boundaries) from continuous DGGS data.

**Implementation:**
1. For each cell, check if any neighbor crosses a threshold value
2. If cell value > threshold and neighbor < threshold (or vice versa), mark as contour
3. Chain contour cells into connected lines
4. Store as new dataset with contour level attribute

```sql
-- Find cells on contour boundary
SELECT a.dggid, a.value_num, :threshold AS contour_level
FROM cell_objects a
JOIN dgg_topology t ON a.dggid = t.dggid
JOIN cell_objects b ON t.neighbor_dggid = b.dggid
    AND b.dataset_id = a.dataset_id AND b.attr_key = a.attr_key
WHERE a.dataset_id = :ds AND a.attr_key = :attr
    AND a.value_num >= :threshold AND b.value_num < :threshold
```

### 4.6 Density Estimation (Kernel Density on DGGS)

**Purpose:** Create smooth density surface from point data.

**Implementation:**
1. For each cell with data, spread value to K-ring neighbors
2. Apply kernel function (Gaussian, Epanechnikov) based on distance
3. Sum contributions from all nearby source cells
4. Normalize by area

### 4.7 Spatial Clustering (DBSCAN on DGGS)

**Purpose:** Find spatial clusters of similar values without pre-specifying count.

**Implementation:**
1. Use topology table for epsilon-neighborhood (K-ring)
2. Core points: cells with >= minPts neighbors within K hops having similar values
3. Border points: within K hops of a core point
4. Noise: neither core nor border
5. Assign cluster IDs, store as new dataset

### 4.8 Change Detection (Multi-Temporal)

**Purpose:** Identify significant spatial changes between time periods.

**Implementation:**
1. Compare two temporal snapshots cell-by-cell
2. Compute change magnitude and direction
3. Apply threshold to identify significant changes
4. Classify change types (gain, loss, conversion)
5. Compute change statistics (area changed, rate)

---

## 5. Architecture Improvements

### 5.1 Operation Pipeline / Chaining

Allow users to chain operations into workflows:
```
Buffer(Dataset_A, k=3) → Intersection(_, Dataset_B) → Aggregate(_, method=sum)
```

**Implementation:** Add a `pipeline` endpoint that accepts ordered operation list, executes sequentially, and only persists the final result.

### 5.2 Lazy Evaluation / Virtual Datasets

Instead of materializing every operation result, support "virtual datasets" that store the operation definition and compute on-the-fly when queried. Only materialize when explicitly requested or when performance demands it.

### 5.3 Undo / Dataset Lineage

Track full operation lineage:
```json
{
  "dataset_id": "result-uuid",
  "operation": "buffer",
  "inputs": ["source-uuid"],
  "parameters": {"iterations": 3},
  "created_at": "...",
  "parent_operations": ["intersection-uuid"]
}
```

Enable "undo" by deleting result dataset and removing from lineage.

### 5.4 Streaming Large Operations

For operations on large datasets (>100K cells):
1. Process in batches of 10K cells
2. Report progress via WebSocket or SSE
3. Allow cancellation mid-operation
4. Resume from last batch on failure

### 5.5 Parallel SQL Execution

Some operations can be parallelized:
- Split dataset by DGGID prefix ranges
- Execute operation on each partition
- Merge results

---

## 6. Data Ingestion Enhancements

### 6.1 Shapefile / GeoPackage Import
Convert vector geometry to DGGS cells:
1. For each polygon, find all DGGS cells whose centroid falls within
2. Assign polygon attributes to those cells
3. Handle multi-polygon features

### 6.2 Multi-Band Raster Import
Current GeoTIFF ingestion only reads band 1.
Enhancement: Read all bands, create separate attr_key per band.

### 6.3 NetCDF / HDF5 Import
Common scientific data formats with built-in temporal dimension.
Map dimensions to DGGS cells + tid.

### 6.4 Area-Weighted Raster Sampling
Instead of point-sampling at centroid:
1. Generate multiple sample points within each DGGS cell
2. Sample raster at each point
3. Average/weight by coverage fraction

### 6.5 Real-Time Streaming Ingestion
Accept streaming data via WebSocket:
- Sensor networks publishing cell updates
- Real-time satellite data feeds
- IoT device telemetry

---

## 7. Performance Optimizations

### 7.1 Topology Table Improvements
- Add `children_dggid` column for faster refinement
- Pre-compute K-ring (k=2,3) as dedicated columns
- Add `distance` column for weighted operations
- Populate lazily on first use per level

### 7.2 Spatial Indexing
- Add GiST index on dggid prefix for range queries
- Use BRIN index on tid for temporal range scans
- Partition cell_objects by level as well as dataset_id

### 7.3 Query Result Caching
- Cache frequent viewport queries in Redis with TTL
- Invalidate on dataset mutation
- Cache topology lookups (neighbor lists are immutable)

### 7.4 Connection Pooling
- Use pgbouncer for connection multiplexing
- Configure statement-level pooling for read-heavy workloads

---

## 8. Priority Implementation Roadmap

### Phase 1: Fix Bugs (Critical)
1. Fix Union COALESCE bug (`ops_service.py:285`)
2. Fix topology check (`ops_service.py:158-164`)
3. Fix correlation formula (`zonal_stats.py:347`)
4. Fix temporal aggregate parameter binding (`temporal.py:285`)
5. Fix hotspot analysis SQL (`zonal_stats.py:400-438`)

### Phase 2: Complete Existing Features (High)
1. Add multi-aggregation methods to Aggregate operation
2. Implement distance-weighted buffer
3. Add symmetric difference operation
4. Fix and complete CA spread rules (probabilistic, directional)
5. Implement temporal snapshot (currently returns metadata only)

### Phase 3: New Core Algorithms (High)
1. Spatial autocorrelation (Moran's I)
2. Contour/isoline generation
3. IDW interpolation
4. Change detection
5. DBSCAN clustering

### Phase 4: Advanced Algorithms (Medium)
1. Watershed/flow accumulation
2. Viewshed analysis
3. Shortest path / network analysis
4. Kernel density estimation
5. Spatial regression

### Phase 5: Architecture (Medium)
1. Operation pipeline/chaining
2. Dataset lineage tracking
3. Streaming large operations
4. Shapefile/GeoPackage import

### Phase 6: ML Integration (Lower)
1. Replace simulated ML with actual scikit-learn
2. Feature extraction from DGGS neighborhoods
3. Model persistence in MinIO
4. Prediction result as real datasets

---

## 9. Quick Wins (< 1 day each)

1. **Fix Union bug** - Change line 285 from `COALESCE(a.tid, b.tid)` to `a.tid = b.tid`
2. **Fix topology check** - Change `== 0` to `is None`
3. **Add aggregation methods** - Parameterize the AVG() in aggregate to accept method
4. **Symmetric difference** - Simple combination of existing difference operations
5. **Proper correlation** - Replace with PostgreSQL `CORR()` built-in
6. **Buffer distance values** - Store `depth` from recursive CTE as `value_num`
7. **Multi-band raster** - Loop over rasterio bands instead of hardcoding band 1
8. **Contour detection** - SQL query comparing cell vs neighbor values across threshold
