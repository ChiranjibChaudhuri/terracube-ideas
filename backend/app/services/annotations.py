"""Collaborative annotation service."""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, or_, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
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
        from app.models_annotations import Annotation, CellAnnotation, AnnotationShare
        import uuid

        # Validate inputs
        try:
            dataset_uuid = uuid.UUID(dataset_id)
        except ValueError:
            raise ValueError("Invalid dataset_id format")
        created_by_uuid = None
        if created_by:
            try:
                created_by_uuid = uuid.UUID(created_by)
            except ValueError:
                raise ValueError("Invalid created_by format")

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

        # Generate annotation ID
        annotation_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # Create annotation record
        annotation = Annotation(
            id=annotation_id,
            cell_dggid=cell_dggid,
            dataset_id=dataset_uuid,
            content=content,
            annotation_type=annotation_type,
            visibility=visibility,
            created_by=created_by_uuid,
            created_at=now,
            updated_at=now,
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
                try:
                    shared_with_uuid = uuid.UUID(user_id)
                except ValueError:
                    raise ValueError("Invalid shared_with user ID format")
                share = AnnotationShare(
                    annotation_id=annotation_id,
                    shared_with=shared_with_uuid,
                    created_at=now
                )
                self.db.add(share)

        await self.db.commit()

        return {
            "id": str(annotation_id),
            "cell_dggid": cell_dggid,
            "dataset_id": dataset_id,
            "content": content,
            "type": annotation_type,
            "visibility": visibility,
            "shared_with": shared_with or [],
            "created_by": created_by,
            "created_at": now.isoformat()
        }

    async def get_annotation(self, annotation_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get details of a specific annotation with visibility checks.
        """
        from app.models_annotations import Annotation, AnnotationShare
        import uuid

        try:
            annotation_uuid = uuid.UUID(annotation_id)
        except ValueError:
            raise ValueError("Invalid annotation_id format")

        # Build query
        stmt = select(Annotation).where(Annotation.id == annotation_uuid)
        result = await self.db.execute(stmt)
        annotation = result.scalars().first()

        if not annotation:
            return None

        # Visibility checks
        if annotation.visibility == AnnotationVisibility.PRIVATE:
            if str(annotation.created_by) != user_id:
                return None
        elif annotation.visibility == AnnotationVisibility.SHARED:
            # Check if user is creator
            if str(annotation.created_by) != user_id:
                if not user_id:
                    return None
                
                # Check shares
                share_stmt = select(AnnotationShare).where(
                    and_(
                        AnnotationShare.annotation_id == annotation_uuid,
                        AnnotationShare.shared_with == uuid.UUID(user_id)
                    )
                )
                share_result = await self.db.execute(share_stmt)
                if not share_result.scalars().first():
                    return None
        
        # Public is visible to everyone

        return {
            "id": str(annotation.id),
            "cell_dggid": annotation.cell_dggid,
            "dataset_id": str(annotation.dataset_id),
            "content": annotation.content,
            "type": annotation.annotation_type,
            "visibility": annotation.visibility,
            "created_by": str(annotation.created_by) if annotation.created_by else None,
            "created_at": annotation.created_at.isoformat() if annotation.created_at else None
        }

    async def get_annotation(self, annotation_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get details of a specific annotation with visibility checks.
        """
        from app.models_annotations import Annotation, AnnotationShare
        import uuid

        try:
            annotation_uuid = uuid.UUID(annotation_id)
        except ValueError:
            raise ValueError("Invalid annotation_id format")

        # Build query
        stmt = select(Annotation).where(Annotation.id == annotation_uuid)
        result = await self.db.execute(stmt)
        annotation = result.scalars().first()

        if not annotation:
            return None

        # Visibility checks
        if annotation.visibility == AnnotationVisibility.PRIVATE:
            if str(annotation.created_by) != user_id:
                return None
        elif annotation.visibility == AnnotationVisibility.SHARED:
            # Check if user is creator
            if str(annotation.created_by) != user_id:
                if not user_id:
                    return None
                
                # Check shares
                share_stmt = select(AnnotationShare).where(
                    and_(
                        AnnotationShare.annotation_id == annotation_uuid,
                        AnnotationShare.shared_with == uuid.UUID(user_id)
                    )
                )
                share_result = await self.db.execute(share_stmt)
                if not share_result.scalars().first():
                    return None
        
        # Public is visible to everyone

        return {
            "id": str(annotation.id),
            "cell_dggid": annotation.cell_dggid,
            "dataset_id": str(annotation.dataset_id),
            "content": annotation.content,
            "type": annotation.annotation_type,
            "visibility": annotation.visibility,
            "created_by": str(annotation.created_by) if annotation.created_by else None,
            "created_at": annotation.created_at.isoformat() if annotation.created_at else None
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
        from app.models_annotations import Annotation
        import uuid

        try:
            dataset_uuid = uuid.UUID(dataset_id)
        except ValueError:
            raise ValueError("Invalid dataset_id format")

        # Build query
        stmt = select(Annotation).where(Annotation.dataset_id == dataset_uuid)

        # Apply filters
        if visibility:
            stmt = stmt.where(Annotation.visibility == visibility)

        if types:
            stmt = stmt.where(Annotation.annotation_type.in_(types))

        if created_by:
            try:
                created_by_uuid = uuid.UUID(created_by)
            except ValueError:
                raise ValueError("Invalid created_by format")
            stmt = stmt.where(Annotation.created_by == created_by_uuid)

        stmt = stmt.order_by(Annotation.created_at.desc()).limit(limit)

        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        annotations = []
        for row in rows:
            annotations.append({
                "id": str(row.id),
                "cell_dggid": row.cell_dggid,
                "dataset_id": str(row.dataset_id),
                "content": row.content,
                "type": row.annotation_type,
                "visibility": row.visibility,
                "created_by": str(row.created_by) if row.created_by else None,
                "created_at": row.created_at.isoformat() if row.created_at else None
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
        from app.models_annotations import Annotation
        import uuid

        try:
            annotation_uuid = uuid.UUID(annotation_id)
        except ValueError:
            raise ValueError("Invalid annotation_id format")

        # Get existing annotation
        result = await self.db.execute(
            select(Annotation).where(Annotation.id == annotation_uuid)
        )
        annotation = result.scalars().first()
        if not annotation:
            raise ValueError(f"Annotation not found: {annotation_id}")

        # Verify user is creator
        if str(annotation.created_by) != user_id:
            raise PermissionError("User can only update their own annotations")

        updates = {}
        if content is not None:
            updates["content"] = content
        if visibility is not None:
            updates["visibility"] = visibility
        if updates:
            updates["updated_at"] = datetime.now(timezone.utc)

        if updates:
            await self.db.execute(
                update(Annotation).where(Annotation.id == annotation_uuid).values(**updates)
            )
            await self.db.commit()

        # Return updated annotation
        result = await self.db.execute(
            select(Annotation).where(Annotation.id == annotation_uuid)
        )
        updated = result.scalars().first()

        return {
            "id": str(updated.id),
            "cell_dggid": updated.cell_dggid,
            "dataset_id": str(updated.dataset_id),
            "content": updated.content,
            "type": updated.annotation_type,
            "visibility": updated.visibility,
            "updated_at": updated.updated_at.isoformat() if updated.updated_at else None
        }

    async def delete_annotation(
        self,
        annotation_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Delete an annotation (only for creator).
        """
        from app.models_annotations import Annotation, CellAnnotation, AnnotationShare
        import uuid

        try:
            annotation_uuid = uuid.UUID(annotation_id)
        except ValueError:
            raise ValueError("Invalid annotation_id format")

        # Get annotation
        result = await self.db.execute(
            select(Annotation).where(Annotation.id == annotation_uuid)
        )
        annotation = result.scalars().first()
        if not annotation:
            raise ValueError(f"Annotation not found: {annotation_id}")

        # Verify ownership
        if str(annotation.created_by) != user_id:
            raise PermissionError("User can only delete their own annotations")

        # Delete shares first
        await self.db.execute(
            delete(AnnotationShare).where(AnnotationShare.annotation_id == annotation_uuid)
        )

        # Delete cell annotations
        await self.db.execute(
            delete(CellAnnotation).where(CellAnnotation.annotation_id == annotation_uuid)
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
        from app.models_annotations import Annotation
        import uuid

        try:
            dataset_uuid = uuid.UUID(dataset_id)
        except ValueError:
            raise ValueError("Invalid dataset_id format")

        # Build search query - use ilike for simple text search
        stmt = select(Annotation).where(
            Annotation.dataset_id == dataset_uuid,
            Annotation.content.ilike(f"%{query}%")
        )

        stmt = stmt.order_by(Annotation.created_at.desc()).limit(limit)

        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        annotations = []
        for row in rows:
            annotations.append({
                "id": str(row.id),
                "cell_dggid": row.cell_dggid,
                "dataset_id": str(row.dataset_id),
                "content": row.content,
                "type": row.annotation_type,
                "visibility": row.visibility,
                "created_by": str(row.created_by) if row.created_by else None,
                "created_at": row.created_at.isoformat() if row.created_at else None
            })

        return {
            "dataset_id": dataset_id,
            "query": query,
            "filters_applied": {"bbox": bbox},
            "annotations": annotations
        }


def get_annotation_service(db: AsyncSession) -> CollaborativeAnnotationService:
    """Create a CollaborativeAnnotationService instance for the given session."""
    return CollaborativeAnnotationService(db)
