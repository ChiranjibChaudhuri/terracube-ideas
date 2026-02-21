"""
Annotations and related models for TerraCube IDEAS
"""

from sqlalchemy import Column, String, Text, ForeignKey, Index, UniqueConstraint, Integer, CheckConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models import Base
import uuid


class Annotation(Base):
    """
    Core annotation record for collaborative notes on DGGS cells.

    Stores the annotation content and metadata separate from cell relationships.
    """
    __tablename__ = "annotations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cell_dggid = Column(String(50), nullable=False, index=True)
    dataset_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    content = Column(Text, nullable=False)
    annotation_type = Column(String(50), nullable=False, default="note")  # note, warning, question, correction, observation
    visibility = Column(String(20), nullable=False, default="private")  # private, shared, public
    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=True)

    __table_args__ = (
        Index("idx_annotations_cell", "cell_dggid"),
        Index("idx_annotations_dataset", "dataset_id"),
        Index("idx_annotations_type", "annotation_type"),
        Index("idx_annotations_visibility", "visibility"),
        Index("idx_annotations_created_by", "created_by"),
    )


class CellAnnotation(Base):
    """
    Cell lookup table for annotations.

    Enables fast cell-based queries for annotation display on map.
    """
    __tablename__ = "cell_annotations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    annotation_id = Column(UUID(as_uuid=True), nullable=False)
    cell_dggid = Column(String(50), nullable=False)

    __table_args__ = (
        Index("idx_cell_annotations_annotation", "annotation_id"),
        Index("idx_cell_annotations_cell", "cell_dggid"),
        UniqueConstraint("annotation_id", "cell_dggid", name="uq_cell_annotations"),
    )


class AnnotationShare(Base):
    """
    Share records for 'shared' visibility annotations.

    Tracks which users can access a specific annotation.
    """
    __tablename__ = "annotation_shares"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    annotation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    shared_with = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(String(50), nullable=False)

    __table_args__ = (
        Index("idx_annotation_shares_annotation", "annotation_id"),
        Index("idx_annotation_shares_user", "shared_with"),
        UniqueConstraint("annotation_id", "shared_with", name="uq_annotation_shares"),
    )
