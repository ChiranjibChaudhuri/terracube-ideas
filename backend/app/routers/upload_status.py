"""
Upload status polling endpoint.
Allows frontend to check the status of an upload/job.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db
from app.models import Upload
from app.auth import get_current_user
from typing import List

router = APIRouter(prefix="/api/uploads", tags=["upload-status"])


class StatusResponse(BaseModel):
    id: str
    status: str
    filename: str
    error: str | None = None
    dataset_id: str | None = None
    created_at: str


@router.get("/{upload_id}")
async def get_upload_status(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Get the status of an upload by ID.
    Returns the current status, any error message, and the resulting dataset ID if available.
    """
    from app.repositories.upload_repo import UploadRepository

    repo = UploadRepository(db)
    try:
        upload = await repo.get_by_id(upload_id)
        if not upload:
            raise HTTPException(status_code=404, detail="Upload not found")

        return {
            "id": str(upload.id),
            "status": upload.status,
            "filename": upload.filename,
            "error": upload.error,
            "dataset_id": str(upload.dataset_id) if upload.dataset_id else None,
            "created_at": upload.created_at.isoformat() if upload.created_at else None
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid upload ID")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_uploads(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    List recent uploads for the current user.
    Useful for showing a history of uploads/jobs.
    """
    from app.repositories.upload_repo import UploadRepository

    repo = UploadRepository(db)
    stmt = select(Upload).order_by(Upload.created_at.desc())

    if status:
        stmt = stmt.where(Upload.status == status)

    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    uploads = result.scalars().all()

    return {
        "uploads": [
            {
                "id": str(u.id),
                "filename": u.filename,
                "status": u.status,
                "error": u.error,
                "dataset_id": str(u.dataset_id) if u.dataset_id else None,
                "created_at": u.created_at.isoformat() if u.created_at else None
            }
            for u in uploads
        ],
        "count": len(uploads),
        "limit": limit,
        "offset": offset
    }
