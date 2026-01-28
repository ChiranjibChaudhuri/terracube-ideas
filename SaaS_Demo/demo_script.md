# TerraCube IDEAS: Advanced DGGS SaaS Demo Script

**Goal:** Showcase the full spectrum of DGGS-native spatial intelligence capabilities.
**Environment:** Docker (http://localhost:8080)
**Admin Credentials:** `admin@terracube.xyz` / `ChangeThisSecurePassword123!`

---

## Scene 1: The Vision
**Action:** Open `http://localhost:8080/`. Scroll through the landing page highlights.
**Key Message:** TerraCube IDEAS is not just another GIS; it's a paradigm shift to table-centric spatial data.
**Overlay Text:** "Grid-Native Spatial Intelligence"

## Scene 2: Unified Access
**Action:** Click "Get Started" -> Login with Admin credentials.
**Key Message:** Secure, high-performance access to global-scale datasets.
**Visual:** Dashboard loading with 2D map view.

## Scene 3: The Global Grid (3D View)
**Action:** 
1. Open "Map Settings".
2. Toggle "3D Globe View".
3. Rotate the globe to show IVEA3H cell alignment at coarse levels.
**Key Message:** Native support for the Earth's curvature. Equal-area cells for global consistency.
**Visual:** The 3D globe with the grid visible.

## Scene 4: Hierarchical Dataset Discovery
**Action:**
1. Open "Add Layer".
2. Search for "Global Temperature".
3. Add the dataset.
4. Pan to a new location and observe the status bar "Loading cells..." as the viewport-based fetching happens.
**Key Message:** Infinite scale through on-demand, resolution-aware data streaming.
**Visual:** Temperature cells populating the map dynamically.

## Scene 5: Styling & Visual Analysis
**Action:**
1. Go to "Toolbox" -> "Style" tab.
2. Change Color Ramp to "plasma".
3. Adjust Opacity to 0.5.
4. Click "Apply Style".
**Key Message:** Instant visual feedback for data exploration.
**Visual:** The map color ramp updates smoothly.

## Scene 6: Spatial Operations (Unary: Buffer)
**Action:**
1. Go to "Toolbox" -> "Tools" tab.
2. Select "Buffer" (K-Ring).
3. Set Layer: "Global Temperature", K-Ring: 2.
4. Click "Run Operation".
5. Observe the new layer "Buffer result" appearing.
**Key Message:** Ad-hoc spatial analysis using pre-computed topology tables. 100x faster than geometry-based spatial joins.
**Visual:** A buffered representation of the data appearing as a new layer.

## Scene 7: Multi-Dataset Intelligence (Binary: Intersection)
**Action:**
1. Search and add another dataset (e.g., "Protected Areas").
2. Go to "Tools" -> "Intersection" (Set Op).
3. Select Layer A (Temperature) and Layer B (Protected Areas).
4. Run Operation.
**Key Message:** Complex multi-layer analysis performed as optimized SQL JOINs.
**Visual:** The intersection of two datasets highlighted on the map.

## Scene 8: Zonal Statistics (Cross-Resolution Analysis)
**Action:**
1. Open "Tools" -> "Zonal Stats".
2. Zone Layer: "Global Regions (Lv2)", Value Layer: "Global Temperature".
3. Run Operation.
**Key Message:** Accurate statistical aggregation across differing grid resolutions.
**Visual:** Region-based averages calculated and displayed.

## Scene 9: High-Intensity Analyst Workbench
**Action:**
1. Navigate to `/workbench`.
2. Toggle the "DGGS ANALYST" sidebar.
3. Show the Deck.gl high-performance rendering of 100k+ cells.
**Key Message:** Pro-grade tools for high-density spatial visualization and complex workflow orchestration.
**Visual:** Massive cell rendering with the high-performance Deck.gl engine.

## Scene 10: Conclusion
**Action:** Return to Dashboard and Sign Out.
**Key Message:** TerraCube IDEAS: The scalable foundation for the next generation of spatial analytics.
**Visual:** Back to Landing Page.
