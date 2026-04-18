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
                    "ignition_dataset_id": {"type": "string", "description": "Starting fire locations"},
                    "fuel_dataset_id": {"type": "string", "description": "Fuel load dataset"},
                    "weather_dataset_id": {"type": "string", "description": "Weather conditions dataset"},
                    "timesteps": {"type": "number", "default": 10, "description": "Simulation timesteps"},
                    "wind_speed": {"type": "number", "default": 10.0, "description": "Wind speed (km/h)"},
                    "wind_direction": {"type": "number", "default": 0.0, "description": "Wind direction (degrees)"},
                    "humidity": {"type": "number", "default": 50.0, "description": "Relative humidity (%)"}
                },
                "required": ["ignition_dataset_id", "fuel_dataset_id", "weather_dataset_id"]
            },
            "tags": ["fire", "simulation"]
        }
    ]
