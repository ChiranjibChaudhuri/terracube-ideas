# API Documentation - New Features

This document describes the new API endpoints added to TerraCube IDEAS.

## Enhanced Statistics (`/api/stats-enhanced`)

Enhanced zonal statistics beyond the basic `/api/stats` endpoint.

### GET /api/stats-enhanced/correlation

Calculate correlation between two datasets' attributes.

**Query Parameters:**
- `zone_dataset_id`: UUID - Zone dataset ID
- `value_dataset_id`: UUID - Value dataset ID
- `zone_key`: string - Attribute key for zones
- `value_key`: string - Attribute key for values
- `method`: string - Correlation method (`pearson` or `spearman`)

**Response:**
```json
{
  "correlation_coefficient": 0.85,
  "p_value": 0.02,
  "method": "pearson"
}
```

### POST /api/stats-enhanced/hotspot

Detect spatial hotspots using Getis-Ord statistics.

**Request Body:**
```json
{
  "dataset_id": "uuid",
  "attribute": "temperature",
  "threshold": 2.0
}
```

**Response:**
```json
{
  "hotspots": ["dggid1", "dggid2", ...],
  "z_scores": {"dggid1": 3.5, "dggid2": 2.8, ...}
}
```

---

## Annotations (`/api/annotations`)

Collaborative annotation system for DGGS cells.

### POST /api/annotations

Create a new annotation.

**Authentication:** Required

**Request Body:**
```json
{
  "dggid": "2240000000",
  "tid": 267,
  "content": "Field observation: Pine species present",
  "visibility": "public",
  "tags": ["pine", "forest"]
}
```

**Response:**
```json
{
  "id": "uuid",
  "dggid": "2240000000",
  "content": "...",
  "created_by": "user_uuid",
  "created_at": "2026-02-14T10:30:00Z"
}
```

### GET /api/annotations

List annotations with filtering.

**Query Parameters:**
- `dggid`: string - Filter by DGGS cell ID
- `tags`: array - Filter by tags
- `visibility`: string - Filter by visibility level
- `search`: string - Full-text search
- `limit`: integer - Max results (default 50)

### GET /api/annotations/{id}

Get a specific annotation.

### PUT /api/annotations/{id}

Update an annotation (only creator).

### DELETE /api/annotations/{id}

Delete an annotation (only creator or admin).

---

## Prediction & ML (`/api/prediction`)

Machine learning and prediction endpoints.

### POST /api/prediction/models

Train a prediction model.

**Request Body:**
```json
{
  "name": "Fire Spread Model 2026",
  "model_type": "fire_spread",
  "dataset_id": "uuid",
  "target_attribute": "burned",
  "feature_attributes": ["fuel", "slope", "wind"],
  "test_split": 0.2
}
```

### POST /api/prediction/fire-spread

Run fire spread simulation using cellular automata.

**Request Body:**
```json
{
  "model_id": "uuid",
  "ignition_cells": ["2240012345", "2240012346"],
  "steps": 100,
  "rules": {
    "burn_threshold": 0.5,
    "spread_probability": 0.3,
    "wind_direction": 270,
    "wind_speed": 15
  }
}
```

**Response:**
```json
{
  "job_id": "uuid",
  "status": "running",
  "result_dataset_id": "uuid"
}
```

---

## Temporal Operations (`/api/temporal`)

Temporal hierarchy and cellular automata operations.

### GET /api/temporal/snapshot

Get data at a specific temporal ID.

**Query Parameters:**
- `dataset_id`: UUID - Dataset ID
- `tid`: integer - Temporal ID (T0-T9)
- `dggids`: array - Optional filter for specific cells

### POST /api/temporal/aggregate

Aggregate data to a coarser temporal resolution.

**Request Body:**
```json
{
  "dataset_id": "uuid",
  "source_level": "hour",
  "target_level": "day",
  "output_name": "Daily Aggregation"
}
```

### POST /api/temporal/ca/initialize

Initialize a cellular automata simulation.

**Supported Rule Types:**
- `fire_spread` - Fire spread simulation
- `epidemic` - Epidemic spread
- `game_of_life` - Conway's Game of Life
- `opinion` - Opinion dynamics
- `custom` - Custom rule set

**Request Body:**
```json
{
  "name": "Forest Growth Simulation",
  "rule_type": "custom",
  "dataset_id": "uuid",
  "state_attribute": "vegetation_density"
}
```

### POST /api/temporal/ca/step

Step a cellular automata simulation forward.

**Request Body:**
```json
{
  "simulation_id": "uuid",
  "steps": 10,
  "save_interval": 5
}
```

---

## OGC API Features (`/api/ogc`)

OGC API Features standard implementation for interoperability.

### GET /api/ogc/conformance

Declaration of OGC API Features conformance.

### GET /api/ogc/collections

List available feature collections.

### GET /api/ogc/collections/{id}

Get a collection (dataset).

### GET /api/ogc/collections/{id}/items

Get items (cells) from a collection.

**Query Parameters:**
- `bbox`: array - Bounding box filter
- `limit`: integer - Max results
- `offset`: integer - Results offset

---

## Common Patterns

### Error Response Format

All errors follow consistent format:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable message",
  "details": {...},
  "status_code": 400
}
```

### Pagination

List endpoints support pagination:

```json
{
  "items": [...],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total": 1500,
    "total_pages": 30
  }
}
```

### Authentication

Most endpoints require authentication via JWT bearer token:

```
Authorization: Bearer <token>
```

Token is obtained from `/api/auth/login` or `/api/auth/register`.