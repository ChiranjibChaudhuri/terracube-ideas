# Marketplace & Adaptive UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Toolbox into a unified Marketplace where Analytics and Data Layers are treated as "Services" with an Adaptive UI (Dynamic Forms).

**Architecture:** Implement a "Service" registry on the backend that exports JSON Schemas for tool inputs. The frontend will use these schemas to render forms dynamically and provide "Smart Pickers" for dataset selection.

**Tech Stack:** FastAPI, Pydantic (JSON Schema), React, Zod (for frontend validation).

---

### Task 1: Backend Service Registry

**Files:**
- Create: `backend/app/routers/marketplace.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_marketplace.py`

- [ ] **Step 1: Create the Marketplace Router**
Define the `Service` model and a basic endpoint to list available analytics.

```python
# backend/app/routers/marketplace.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

class Service(BaseModel):
    id: str
    name: str
    type: str # DATA_SOURCE | ANALYTIC
    description: str
    input_schema: Dict[str, Any]
    tags: List[str]

@router.get("/services", response_model=List[Service])
async def list_services():
    return [
        {
            "id": "fire-spread",
            "name": "Fire Spread Prediction",
            "type": "ANALYTIC",
            "description": "Cellular Automata fire propagation model.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ignition_dataset_id": {"type": "string", "description": "Source dataset"},
                    "wind_speed": {"type": "number", "default": 10.0}
                },
                "required": ["ignition_dataset_id"]
            },
            "tags": ["fire", "simulation"]
        }
    ]
```

- [ ] **Step 2: Register Router in main.py**
```python
# backend/app/main.py
from app.routers import marketplace
# ...
app.include_router(marketplace.router)
```

- [ ] **Step 3: Verify via Curl**
Run: `curl http://localhost:8000/api/marketplace/services`
Expected: JSON array containing the fire-spread service.

---

### Task 2: Frontend Marketplace Types & Discovery

**Files:**
- Create: `frontend/src/types/marketplace.ts`
- Create: `frontend/src/components/MarketplaceSidebar.tsx`
- Modify: `frontend/src/components/ToolboxPanel.tsx`

- [ ] **Step 1: Define TypeScript Types**
```typescript
// frontend/src/types/marketplace.ts
export type ServiceType = 'DATA_SOURCE' | 'ANALYTIC';

export interface Service {
    id: string;
    name: string;
    type: ServiceType;
    description: string;
    input_schema: any;
    tags: string[];
}
```

- [ ] **Step 2: Implement Marketplace Sidebar**
Create a component to browse/filter services.
- [ ] **Step 3: Refactor ToolboxPanel**
Replace the hard-coded ToolPalette with the new MarketplaceSidebar.

---

### Task 3: Adaptive UI (Dynamic Form)

**Files:**
- Create: `frontend/src/components/DynamicForm.tsx`

- [ ] **Step 1: Implement JSON Schema to Form logic**
Use a library or manual mapping to render inputs based on `input_schema`.
- [ ] **Step 2: Add "Smart Picker" for datasets**
When a property name contains `dataset_id`, render a dropdown that fetches available datasets.

---

### Task 4: End-to-End Wiring

**Files:**
- Modify: `frontend/src/components/ToolboxPanel.tsx`

- [ ] **Step 1: Handle Execution**
When a Marketplace service is executed, call the corresponding backend endpoint (e.g., `/api/prediction/fire/spread`).
- [ ] **Step 2: Test with Fire Spread**
Launch the "Fire Spread" service from the Marketplace and verify the API call is structured correctly.
