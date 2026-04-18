# Design Spec: TerraCube IDEAS Production Readiness & Marketplace

**Date:** 2026-04-18  
**Status:** Draft / User Review  
**Topic:** Frontend Feature Parity, Marketplace Architecture, and Simulation Lifecycle

## 1. Vision & Philosophy
TerraCube IDEAS will evolve from a specialized DGGS tool into a **Data & Analytics Marketplace**. The platform treats both static data layers and dynamic processing algorithms as unified "Services." This design emphasizes production stability, interactive simulation, and collaborative spatial analysis.

---

## 2. Marketplace Architecture (Unified Service Model)
The core of the redesign is the transition to a marketplace-driven UI.

### 2.1 Unified Service Entity
- **Schema:** Every data source and algorithm is registered as a `Service` in the backend.
- **Metadata:** Includes `id`, `type` (DATA_SOURCE | ANALYTIC), `input_schema` (JSON Schema), and `tags`.
- **Discovery:** A searchable sidebar categorized by domain (Fire, Hydrology, etc.).

### 2.2 Adaptive UI Engine
- **DynamicForm:** A reusable frontend component that renders input fields automatically based on a Service's `input_schema`.
- **Smart Pickers:** Specialized UI components for "Dataset" inputs that auto-filter the marketplace for compatible layers based on DGGS level and geographic extent.
- **Workflow:** 
  1. User selects "Fire Spread" (Analytic Service).
  2. UI adapts to show fields for Ignition Source, Fuel Model, and Weather.
  3. User uses Smart Pickers to find relevant Data Source Services.

---

## 3. Simulation & Temporal Lifecycle
Handling long-running simulations (e.g., Fire Spread) with high interactivity.

### 3.1 Live Job Progress
- **Asynchronous Execution:** Clicking "Execute" returns a `job_id`.
- **Progress Layer:** A new entry appears in the Layer List with a real-time progress bar.
- **Streaming Updates:** The MapView polls/receives intermediate DGGS snapshots, showing the simulation "grow" in real-time.

### 3.2 Temporal Playback (Scrubbing)
- **Scrubbable Results:** Completed simulations are saved as Temporal Datasets.
- **Time Controller:** A playback UI (Play/Pause/Scrub) appears at the bottom of the map.
- **Efficiency:** Scrubbing updates the `tid` parameter, triggering surgical DGGS cell fetches for the specific time-slice.

---

## 4. Collaborative Annotations
Integrating the existing backend annotation system into the MapView.

- **Interaction:** Right-click or Inspector-click to "Add Note" to a specific `dggid`.
- **Visibility:** Toggle between Private, Shared (Team), and Public.
- **Indicators:** Annotated cells are visually highlighted on the map; a global "Annotation Feed" allows for rapid navigation between AOIs (Areas of Interest).

---

## 5. Roadmap for Production Readiness
- **Infrastructure:** Implement Alembic for database migrations.
- **Quality:** Establish a `pytest` suite for the Core Spatial Engine.
- **Monetization (Future):** Provisions for Credit-based execution costs and RBAC-driven access control.

---

## 6. Implementation Strategy
1. **Refactor ToolboxPanel:** Move from hard-coded tools to the Marketplace/DynamicForm model.
2. **Wire Prediction API:** Connect the existing `prediction.py` router to the new Adaptive UI.
3. **Enhance MapView:** Add support for temporal scrubbing and annotation indicators.
4. **Backend Stability:** Add Alembic and initial test suite.
