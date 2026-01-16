from sqlalchemy import Column, String, Integer, MetaData, ForeignKey, JSON, Double, DateTime, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String)
    dggs_name = Column(String, default='IVEA3H')
    level = Column(Integer)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    status = Column(String, default="active")
    metadata_ = Column("metadata", JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Upload(Base):
    __tablename__ = "uploads"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"))
    filename = Column(String, nullable=False)
    mime_type = Column(String)
    size_bytes = Column(BigInteger)
    storage_key = Column(String, nullable=False)
    status = Column(String, default="staged")
    error = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

# Note: cell_objects is massive and uses partitioning by dataset_id.
# The composite primary key (id, dataset_id) is required for proper ORM operation.
class CellObject(Base):
    __tablename__ = "cell_objects"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), primary_key=True, nullable=False)
    dggid = Column(String, nullable=False)
    tid = Column(Integer, nullable=False)
    attr_key = Column(String, nullable=False)
    value_text = Column(String)
    value_num = Column(Double)
    value_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
