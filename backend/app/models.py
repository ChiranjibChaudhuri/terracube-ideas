from sqlalchemy import Column, String, Integer, MetaData, ForeignKey, JSON, Double, DateTime, BigInteger, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import uuid
from enum import Enum

Base = declarative_base()

# Import annotation models
from app.models_annotations import Annotation, CellAnnotation, AnnotationShare


class UserRole(str, Enum):
    """User roles for RBAC."""
    ADMIN = "admin"      # Full system access
    EDITOR = "editor"    # Can create/edit datasets
    VIEWER = "viewer"    # Read-only access


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String)
    role = Column(String, default="viewer", nullable=False)  # admin, editor, viewer
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission based on role."""
        permissions = {
            "admin": [
                "create_dataset", "edit_any_dataset", "delete_any_dataset",
                "create_user", "edit_user", "delete_user",
                "manage_system", "view_any_dataset",
                "run_any_operation", "delete_any_operation",
            ],
            "editor": [
                "create_dataset", "edit_own_dataset", "delete_own_dataset",
                "view_any_dataset", "run_any_operation",
            ],
            "viewer": [
                "view_own_dataset", "view_any_dataset",
            ],
        }
        return permission in permissions.get(self.role, [])

    def can_edit_dataset(self, dataset: 'Dataset') -> bool:
        """Check if user can edit a dataset."""
        if self.role == "admin":
            return True
        return self.role in ["editor"] and dataset.created_by == self.id

    def can_delete_dataset(self, dataset: 'Dataset') -> bool:
        """Check if user can delete a dataset."""
        if self.role == "admin":
            return True
        return self.role in ["editor"] and dataset.created_by == self.id

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
    # Visibility: private (only creator), shared (specific users), public (everyone)
    visibility = Column(String, default="private", nullable=False)
    # List of user IDs who have explicit access (for shared visibility)
    shared_with = Column(ARRAY(UUID(as_uuid=True)), default=[])
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
