from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Date
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy import ForeignKey
from sqlalchemy.sql import func
import uuid

from app.models import Base


class StacCatalog(Base):
    __tablename__ = "stac_catalogs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    api_url = Column(String, nullable=False)
    catalog_type = Column(String, nullable=False, default="api")
    auth_type = Column(String, nullable=True)
    collections = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StacCollection(Base):
    __tablename__ = "stac_collections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    catalog_id = Column(UUID(as_uuid=True), ForeignKey("stac_catalogs.id", ondelete="SET NULL"))
    stac_collection = Column(String, nullable=False)
    bbox = Column(ARRAY(Float), nullable=True)
    date_start = Column(Date, nullable=True)
    date_end = Column(Date, nullable=True)
    query_params = Column(JSONB, default=dict)
    scene_count = Column(Integer, default=0)
    index_path = Column(String, nullable=True)
    status = Column(String, nullable=False, default="indexing")
    error = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StacScene(Base):
    __tablename__ = "stac_scenes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("stac_collections.id", ondelete="CASCADE"), nullable=False)
    stac_item_id = Column(String, nullable=False)
    datetime = Column(DateTime(timezone=True), nullable=True)
    cloud_cover = Column(Float, nullable=True)
    bbox = Column(ARRAY(Float), nullable=True)
    bands = Column(JSONB, default=dict)
    properties = Column(JSONB, default=dict)
    thumbnail_url = Column(String, nullable=True)
    dggs_coverage = Column(ARRAY(String), default=list)
    ingested = Column(Boolean, nullable=False, default=False)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
