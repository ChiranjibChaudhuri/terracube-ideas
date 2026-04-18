from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

class JobResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    status: str
    progress: int
    result_dataset_id: Optional[uuid.UUID] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        populate_by_name = True

class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
