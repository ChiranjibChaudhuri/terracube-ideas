from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.repositories.upload_repo import UploadRepository
from app.repositories.dataset_repo import DatasetRepository
from app.services.ingest import process_upload
from app.auth import get_current_user
import shutil
import os
import uuid
from typing import Optional

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    dataset_id: str = Form(""),
    dataset_name: str = Form("", alias="datasetName"),
    dataset_description: str = Form("", alias="datasetDescription"),
    attr_key: str = Form("", alias="attrKey"),
    min_level: Optional[int] = Form(None, alias="minLevel"),
    max_level: Optional[int] = Form(None, alias="maxLevel"),
    source_type: str = Form("", alias="sourceType"),
    dggs_name: str = Form("IVEA3H"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    # Save file to disk
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    dataset_repo = DatasetRepository(db)
    ds_uuid = None
    if dataset_id:
        try:
            ds_uuid = uuid.UUID(dataset_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid dataset_id")
        existing = await dataset_repo.get_by_id(ds_uuid)
        if not existing:
            raise HTTPException(status_code=404, detail="Dataset not found")
    else:
        name = dataset_name.strip() or os.path.splitext(file.filename or "Dataset")[0]
        metadata = {}
        if attr_key:
            metadata["attr_key"] = attr_key
        if min_level is not None:
            metadata["min_level"] = min_level
        if max_level is not None:
            metadata["max_level"] = max_level
        if source_type:
            metadata["source_type"] = source_type

        created = await dataset_repo.create(
            name=name,
            description=dataset_description.strip() or None,
            dggs_name=dggs_name,
            level=min_level if min_level is not None and min_level == max_level else None,
            metadata_=metadata or {},
        )
        ds_uuid = created.id

    # Trigger background processing via Celery
    process_upload.delay(
        str(file_id),
        file_path,
        str(ds_uuid),
        dggs_name,
        attr_key or None,
        min_level,
        max_level,
        source_type or None,
    )

    # Store metadata in DB using Repo
    repo = UploadRepository(db)
    await repo.create(
        id=uuid.UUID(file_id),
        dataset_id=ds_uuid,
        filename=file.filename,
        storage_key=file_path,
        mime_type=file.content_type,
        size_bytes=os.path.getsize(file_path),
        status='processing'
    )
    await db.commit()
        
    return {"id": file_id, "status": "processing", "dataset_id": str(ds_uuid)}
