"""Annotation models for collaborative DGGS notes."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.models import Base


class Annotation(Base):
    """Primary annotation record."""
    __tablename__ = "annotations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cell_dggid = Column(String(50), nullable=False, index=True)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    annotation_type = Column(String(50), nullable=False, default="note")
    visibility = Column(String(20), nullable=False, default="private")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_annotations_cell", "cell_dggid"),
        Index("idx_annotations_dataset", "dataset_id"),
        Index("idx_annotations_type", "annotation_type"),
        Index("idx_annotations_visibility", "visibility"),
        Index("idx_annotations_created_by", "created_by"),
    )


class CellAnnotation(Base):
    """Lookup table for cell-to-annotation joins."""
    __tablename__ = "cell_annotations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    annotation_id = Column(UUID(as_uuid=True), ForeignKey("annotations.id", ondelete="CASCADE"), nullable=False)
    cell_dggid = Column(String(50), nullable=False)

    __table_args__ = (
        Index("idx_cell_annotations_annotation", "annotation_id"),
        Index("idx_cell_annotations_cell", "cell_dggid"),
        UniqueConstraint("annotation_id", "cell_dggid", name="uq_cell_annotations"),
    )


class AnnotationShare(Base):
    """Share records for annotations with shared visibility."""
    __tablename__ = "annotation_shares"

    id = Column(Integer, primary_key=True, autoincrement=True)
    annotation_id = Column(UUID(as_uuid=True), ForeignKey("annotations.id", ondelete="CASCADE"), nullable=False, index=True)
    shared_with = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_annotation_shares_annotation", "annotation_id"),
        Index("idx_annotation_shares_user", "shared_with"),
        UniqueConstraint("annotation_id", "shared_with", name="uq_annotation_shares"),
    )
