# Temporal Simulation & Scrubbing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable multi-step simulations (Fire Spread) with real-time progress tracking and temporal playback (scrubbing) on the map.

**Architecture:** 
- **Backend:** A `Job` model tracks simulation progress. Simulations are executed as background tasks that store results with incremental `tid` (temporal IDs).
- **Frontend:** `MapView` is updated to respect `tid`. A new `TemporalController` provides playback UI. `ToolboxPanel` polls for job status.

**Tech Stack:** FastAPI, SQLAlchemy, React, Deck.gl.

---

### Task 1: Backend Job Tracking

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/app/routers/jobs.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/prediction.py`

- [ ] **Step 1: Add Job Model**
Add the `Job` model to `backend/app/models.py`.

```python
class Job(Base):
    __tablename__ = "jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    status = Column(String, default="pending")
    progress = Column(Integer, default=0)
    result_dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=True)
    metadata_ = Column("metadata", JSON, default={})
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
```

- [ ] **Step 2: Create Jobs Router**
Implement `/api/jobs/{job_id}` to allow the frontend to poll for status.

- [ ] **Step 3: Update Fire Spread Service**
Modify `FireSpreadPredictionService.predict_fire_spread` to:
1. Create a `Job` record.
2. Store simulation results with incremental `tid` (0 to `timesteps-1`).
3. Update `Job.progress` after each simulated step.
4. Set status to `completed` when done.

---

### Task 2: MapView Temporal Support

**Files:**
- Modify: `frontend/src/components/MapView.tsx`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Update API calls**
Ensure `fetchCellsByDggids` in `lib/api.ts` correctly passes the `tid` parameter to the backend `/api/datasets/{dataset_id}/cells` endpoint.

- [ ] **Step 2: MapView Reactivity**
Update `MapView` to re-trigger the viewport update when the `tid` prop changes. This is already partially handled by `extentKey`, but ensure `tid` is correctly used in the fetch.

---

### Task 3: Temporal Playback UI

**Files:**
- Create: `frontend/src/components/TemporalController.tsx`
- Modify: `frontend/src/App.tsx` (or where the map is hosted)

- [ ] **Step 1: Implement TemporalController**
Create a component with:
- A range slider (0 to max timesteps).
- Play/Pause toggle.
- Auto-incrementing timer for playback.

- [ ] **Step 2: Context/Store Integration**
Add `currentTid` and `maxTid` to the app store (`useAppStore`).
When a temporal layer is active, show the `TemporalController`.

---

### Task 4: Job Progress UI

**Files:**
- Modify: `frontend/src/components/ToolboxPanel.tsx`

- [ ] **Step 1: Polling Logic**
When a service execution returns a `job_id`, start a `setInterval` to poll `/api/jobs/{job_id}`.

- [ ] **Step 2: Progress Display**
Show a progress bar in the Toolbox while the job is `running`. Once `completed`, load the final dataset.
