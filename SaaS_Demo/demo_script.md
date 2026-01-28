# TerraCube IDEAS: Advanced DGGS SaaS Demo Script

**Goal:** Showcase DGGS-native spatial analytics with clean dataset/result separation and high-quality basemaps.
**Environment:** Docker (http://localhost:8080)
**Admin Credentials:** `admin@terracube.xyz` / `ChangeThisSecurePassword123!`

---

## Preflight (2–3 minutes)
**Action:** Confirm data-init ran and datasets are available.
**Expected Datasets (8 total):**
- World Countries (vector)
- Canada Boundaries (vector)
- Global Elevation (ETOPO1)
- Global Temperature (WorldClim)
- Dubai DEM (PlanetDEM 1s)
- Kilimanjaro DEM (PlanetDEM 3s)
- USGS DEM Sample (o41078a5)
- USGS DEM Sample (i30dem)

**Note:** Operation results appear only in the **Results** tab and are auto-cleaned after a TTL (default 24h).

---

## Scene 1: The Vision
**Action:** Open `http://localhost:8080/`. Scroll the landing page highlights.
**Key Message:** TerraCube IDEAS is not just GIS; it is a grid-native operating system for spatial intelligence.
**Overlay Text:** “Grid-Native Spatial Intelligence”

## Scene 2: Secure Access
**Action:** Click “Get Started” → Log in with Admin credentials.
**Key Message:** Secure, high-performance access to global-scale DGGS datasets.
**Visual:** Dashboard with 2D map view and empty layer list.

## Scene 3: Basemap Quality (Unified Selection)
**Action:**
1. Open **Map Settings**.
2. Select **Basemap** "Voyager + Blue Marble HD."
3. Toggle **3D Globe View** ON.
4. Rotate and zoom the globe.
**Key Message:** Unified basemap selection simplifies high-quality visualization across flat and globe views.
**Visual:** High-quality earth texture in globe view defaults to Blue Marble HD.

## Scene 4: Dataset vs Results (Clean Separation)
**Action:**
1. Open **Add Layer**.
2. Confirm two tabs: **Datasets** and **Results**.
3. Use **Datasets** tab only; **Results** should be empty at the start.
4. Search for “Global Temperature” and add it.
**Key Message:** Datasets and operation outputs are separated for clarity.
**Visual:** Dataset added in layers; Results tab still empty.

## Scene 5: Resolution Control (Zoom Offset)
**Action:**
1. In **Map Settings**, keep **Resolution Mode = Auto**.
2. Adjust **Zoom Offset** to **+3** (default). Try +4 if you want finer cells.
3. Zoom in/out and observe resolution changes.
**Key Message:** Level selection is zoom-aware and tunable.
**Visual:** Cell granularity tightens as you zoom in.

## Scene 6: Regional Raster Detail
**Action:**
1. Add “Dubai DEM (PlanetDEM 1s).”
2. Pan to Dubai (approx. 25.2 N, 55.3 E).
3. Toggle between flat and globe to show the same raster.
**Key Message:** High-resolution regional rasters for precision analytics.
**Visual:** DEM cells show local elevation variation.

## Scene 7: Vector Context Layer
**Action:**
1. Add “Canada Boundaries.”
2. Pan to Canada.
3. In **Toolbox → Style**, set Color Ramp to “elevation” and opacity to ~0.6.
**Key Message:** Fast vector overlays with instant styling.
**Visual:** Canada boundary cells overlay the raster.

## Scene 8: Spatial Operation (Unary Buffer)
**Action:**
1. Go to **Toolbox → Tools**.
2. Select **Buffer**.
3. Layer: “Canada Boundaries,” Rings: 2 → **Run Tool**.
4. Open **Add Layer → Results** and add “Buffer result.”
**Key Message:** Spatial operations create clean, separate result datasets.
**Visual:** Buffered Canada layer appears; Results tab count increases.

## Scene 9: Spatial Operation (Binary Intersection)
**Action:**
1. Add “World Countries.”
2. Go to **Tools → Intersection**.
3. Layer A: “World Countries,” Layer B: “Canada Boundaries” → **Run Tool**.
4. Add “Intersection result” from **Results** tab.
**Key Message:** Grid-native overlay operations via optimized DGGS set math.
**Visual:** Result layer matches Canada within the global boundary dataset.

## Scene 10: Wrap-Up
**Action:**
1. Point out **Results** are ephemeral (TTL cleanup).
2. Return to Dashboard and Sign Out.
**Key Message:** TerraCube IDEAS delivers scalable, clean, and high-performance spatial analytics.
**Visual:** Back to landing page.
