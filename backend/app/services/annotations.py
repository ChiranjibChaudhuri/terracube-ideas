"""
Collaborative Annotation Service for TerraCube IDEAS

Allows users to share notes and mark cells with shared/private/public visibility
for collaborative GIS analysis.
"""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)


class AnnotationVisibility:
    """Visibility levels for annotations."""
    PRIVATE = "private"  # Only creator
    SHARED = "shared"  # Shared with specified users
    PUBLIC = "public"  # Visible to all users


class AnnotationType:
    """Types of annotations."""
    NOTE = "note"  # General note or comment
    WARNING = "warning"  # Data quality warning
    QUESTION = "question"  # Question for clarification
    CORRECTION = "correction"  # Suggested data correction
    OBSERVATION = "observation"  # Field observation


class CollaborativeAnnotationService:
    """
    Manages collaborative annotations on DGGS cells.

    Features:
    - Create cell-level annotations
    - List annotations by dataset/viewport/bbox
    - Share annotations with specific users
    - Public/private visibility control
    - Annotation history tracking
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_annotation(
        self,
        cell_dggid: str,
        dataset_id: str,
        content: str,
        annotation_type: str = AnnotationType.NOTE,
        visibility: str = AnnotationVisibility.PRIVATE,
        shared_with: Optional[List[str]] = None,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new annotation on a cell.
        """
        from app.models import Dataset
        import uuid

        # Validate inputs
        try:
            dataset_uuid = uuid.UUID(dataset_id)
        except ValueError:
            raise ValueError(f"Invalid dataset_id format")

        # Validate visibility
        valid_visibilities = [
            AnnotationVisibility.PRIVATE,
            AnnotationVisibility.SHARED,
            AnnotationVisibility.PUBLIC
        ]
        if visibility not in valid_visibilities:
            raise ValueError(f"Invalid visibility: {visibility}")

        # Validate annotation type
        valid_types = [
            AnnotationType.NOTE,
            AnnotationType.WARNING,
            AnnotationType.QUESTION,
            AnnotationType.CORRECTION,
            AnnotationType.OBSERVATION
        ]
        if annotation_type not in valid_types:
            raise ValueError(f"Invalid annotation_type: {annotation_type}")

        # Get creator from created_by (or use provided)
        creator_id = created_by
        if not creator_id and shared_with:
            # Default to first shared user
            creator_id = shared_with[0]

        # Generate annotation ID
        annotation_id = uuid.uuid4()

        # Insert annotation
        from app.models import Annotation, CellAnnotation

        async with self.db.begin():
            # Create annotation record
            annotation = Annotation(
                id=annotation_id,
                cell_dggid=cell_dggid,
                dataset_id=dataset_uuid,
                content=content,
                annotation_type=annotation_type,
                visibility=visibility,
                created_by=creator_id
            )
            self.db.add(annotation)

            # Create cell annotation record (for lookups)
            cell_annotation = CellAnnotation(
                annotation_id=annotation_id,
                cell_dggid=cell_dggid
            )

            self.db.add(cell_annotation)

            # Handle sharing
            if visibility == AnnotationVisibility.SHARED and shared_with:
                for user_id in shared_with:
                    share = Annotation(
                        id=uuid.uuid4(),
                        annotation_id=annotation_id,
                        shared_with=user_id
                    )
                    self.db.add(share)

            await self.db.commit()

        # Fetch created annotation with relations
        result = await self.db.execute(
            select(Annotation).where(Annotation.id == annotation_id)
        )

        return {
            "id": str(annotation_id),
            "cell_dggid": cell_dggid,
            "dataset_id": dataset_id,
            "content": content,
            "type": annotation_type,
            "visibility": visibility,
            "shared_with": shared_with or [],
            "created_by": creator_id,
            "created_at": result["created_at"].isoformat() if result["created_at"] else None
        }

    async def list_annotations(
        self,
        dataset_id: str,
        bbox: Optional[List[float]] = None,
        visibility: Optional[str] = None,
        types: Optional[List[str]] = None,
        created_by: Optional[str] = None,
        limit: int = 1000
    ) -> Dict[str, Any]:
        """
        List annotations with optional filters.
        """
        from app.models import Annotation, CellAnnotation, Dataset
        import uuid

        try:
            dataset_uuid = uuid.UUID(dataset_id)
        except ValueError:
            raise ValueError(f"Invalid dataset_id format")

        # Build query
        stmt = select(Annotation).where(Annotation.dataset_id == dataset_uuid)

        # Apply filters
        if bbox and len(bbox) == 4:
            # Filter by bbox - requires DGGAL for centroid lookup
            # For now, fetch all and filter in Python
            pass

        if visibility:
            stmt = stmt.where(Annotation.visibility == visibility)

        if types:
            stmt = stmt.where(Annotation.annotation_type.in_(types))

        if created_by:
            stmt = stmt.where(Annotation.created_by == created_by)

        stmt = stmt.order_by(Annotation.created_at.desc()).limit(limit)

        result = await self.db.execute(stmt)

        annotations = []
        for row in result.mappings():
            annotations.append({
                "id": str(row["id"]),
                "cell_dggid": row["cell_dggid"],
                "dataset_id": row["dataset_id"],
                "content": row["content"],
                "type": row["annotation_type"],
                "visibility": row["visibility"],
                "created_by": str(row["created_by"]) if row["created_by"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None
            })

        return {
            "dataset_id": dataset_id,
            "filters_applied": {
                "bbox": bbox,
                "visibility": visibility,
                "types": types,
                "created_by": created_by
            },
            "annotations": annotations
        }

    async def update_annotation(
        self,
        annotation_id: str,
        content: Optional[str] = None,
        visibility: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update an existing annotation (only for creator).
        """
        from app.models import Annotation
        import uuid

        try:
            annotation_uuid = uuid.UUID(annotation_id)
        except ValueError:
            raise ValueError(f"Invalid annotation_id format")

        # Get existing annotation
        result = await self.db.execute(
            select(Annotation).where(Annotation.id == annotation_uuid)
        )
        annotation = result.first()
        if not annotation:
            raise ValueError(f"Annotation not found: {annotation_id}")

        # Verify user is creator or shared with
        is_owner = annotation.created_by == user_id
        is_shared = user_id in (annotation.shared_with or [])

        if not is_owner and not is_shared:
            raise ValueError("User can only update their own annotations or annotations shared with them")

        updates = {}
        if content is not None:
            updates["content"] = content
        if visibility is not None:
            updates["visibility"] = visibility

        if updates:
            await self.db.execute(
                update(Annotation.__table__)
                .where(Annotation.id == annotation_uuid)
                .values(**updates)
            )
            await self.db.commit()

        # Return updated annotation
        result = await self.db.execute(
            select(Annotation).where(Annotation.id == annotation_uuid)
        )
        return {
            "id": str(result["id"]),
            "cell_dggid": result["cell_dggid"],
            "dataset_id": result["dataset_id"],
            "content": result["content"],
            "type": result["annotation_type"],
            "visibility": result["visibility"],
            "updated_at": datetime.now().isoformat()
        }

    async def delete_annotation(
        self,
        annotation_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Delete an annotation (only for creator).
        """
        from app.models import Annotation
        import uuid

        try:
            annotation_uuid = uuid.UUID(annotation_id)
        except ValueError:
            raise ValueError(f"Invalid annotation_id format")

        # Get annotation with sharing info
        result = await self.db.execute(
            select(Annotation, Annotation.shared_with)
            .where(Annotation.id == annotation_uuid)
        )
        annotation = result.first()
        if not annotation:
            raise ValueError(f"Annotation not found: {annotation_id}")

        # Verify ownership
        is_owner = annotation.created_by == user_id
        is_shared = user_id in (annotation.shared_with or [])

        if not is_owner:
            raise ValueError("User can only delete their own annotations")

        # Delete shares first
        if annotation.shared_with:
            await self.db.execute(
                delete(Annotation.__table__)
                .where(Annotation.annotation_id.in_(annotation.shared_with))
            )

        # Delete annotation
        await self.db.execute(
            delete(Annotation).where(Annotation.id == annotation_uuid)
        )
        await self.db.commit()

        return {"deleted": True}

    async def search_annotations(
        self,
        dataset_id: str,
        query: str,
        bbox: Optional[List[float]] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Full-text search across annotation content.
        """
        from app.models import Annotation
        import uuid

        try:
            dataset_uuid = uuid.UUID(dataset_id)
        except ValueError:
            raise ValueError(f"Invalid dataset_id format")

        # Build search query
        stmt = select(Annotation).where(
            Annotation.dataset_id == dataset_uuid,
            Annotation.content.ilike(f"%{query}%")
        )

        if bbox and len(bbox) == 4:
            # BBox filter would require DGGAL to filter by cell location
            # For now, return all and let frontend filter
            pass

        stmt = stmt.order_by(Annotation.created_at.desc()).limit(limit)

        result = await self.db.execute(stmt)

        annotations = []
        for row in result.mappings():
            annotations.append({
                "id": str(row["id"]),
                "cell_dggid": row["cell_dggid"],
                "dataset_id": row["dataset_id"],
                "content": row["content"],
                "type": row["annotation_type"],
                "visibility": row["visibility"],
                "created_by": str(row["created_by"]) if row["created_by"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None
            })

        return {
            "dataset_id": dataset_id,
            "query": query,
            "filters_applied": {"bbox": bbox},
            "annotations": annotations
        }


# Singleton instance
_annotation_service = None

def get_annotation_service(db: AsyncSession) -> CollaborativeAnnotationService:
    """Get or create singleton CollaborativeAnnotationService instance."""
    global _annotation_service
    if _annotation_service is None:
        _annotation_service = CollaborativeAnnotationService(db)
    return _annotation_service
