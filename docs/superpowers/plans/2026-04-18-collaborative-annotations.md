# Collaborative Annotations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bridge the backend annotation system to the map interface, allowing users to create "Sticky Notes" on DGGS cells and share them in a collaborative workspace.

**Architecture:** 
- **Backend:** Complete the `get_annotation` endpoint and ensure list filtering by visibility/user is robust.
- **Frontend:** 
  - `AnnotationPanel`: A side drawer for listing/searching annotations.
  - `CellInspector`: Update to allow creating/viewing annotations.
  - `MapView`: Add a new layer to render "indicator" icons on annotated cells.
  - `AppStore`: Sync annotations globally.

**Tech Stack:** FastAPI, SQLAlchemy, React, Deck.gl (IconLayer or ScatterplotLayer).

---

### Task 1: Backend Completion

**Files:**
- Modify: `backend/app/routers/annotations.py`
- Modify: `backend/app/services/annotations.py`
- Test: `backend/tests/test_annotations.py`

- [ ] **Step 1: Implement `get_annotation` Router**
Fill in the `Not yet implemented` 501 endpoint in `backend/app/routers/annotations.py`.

- [ ] **Step 2: Add `get_annotation` Service Method**
Add a method to `CollaborativeAnnotationService` to fetch a single annotation with permission checks.

- [ ] **Step 3: Write Integration Test**
Verify that a user can create an annotation and then retrieve it.

---

### Task 2: Frontend API & Store Integration

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/store.ts`

- [ ] **Step 1: Add Annotation API Methods**
Implement `fetchAnnotations(datasetId)`, `createAnnotation(params)`, and `deleteAnnotation(id)`.

- [ ] **Step 2: Sync Annotations in Store**
Add an `annotations: Annotation[]` array and `setAnnotations` action to the zustand store.

---

### Task 3: Map Visualization & Interaction

**Files:**
- Modify: `frontend/src/components/MapView.tsx`
- Modify: `frontend/src/pages/Workbench.tsx`

- [ ] **Step 1: Render Annotation Indicators**
Add a `ScatterplotLayer` or `IconLayer` to `MapView.tsx` that renders markers on cells found in the `annotations` store.

- [ ] **Step 2: Update Inspector with Annotation UI**
Modify the `Cell Inspector` panel in `MapView` to show a "Add Note" button and list existing notes for the selected cell.

---

### Task 4: Collaborative Workspace Panel

**Files:**
- Create: `frontend/src/components/AnnotationFeed.tsx`
- Modify: `frontend/src/pages/Workbench.tsx`

- [ ] **Step 1: Implement AnnotationFeed**
Create a side panel that lists all annotations for the active dataset. 
- Clicking an annotation should "Jump" the map to that cell.

- [ ] **Step 2: Real-time Refresh**
Add a simple "Refresh" button or a basic polling mechanism (similar to Jobs) to keep the feed updated when collaborating with others.
