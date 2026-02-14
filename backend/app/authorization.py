"""
Role-Based Access Control (RBAC) authorization module.

Provides FastAPI dependencies for checking user permissions
on datasets and other resources.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid

from app.models import User, Dataset, UserRole
from app.auth import get_current_user


class PermissionChecker:
    """
    Utility class for checking user permissions.

    Roles:
    - admin: Full access to everything
    - editor: Can create/edit/delete own datasets, view any dataset
    - viewer: Can view public datasets or own datasets
    """

    @staticmethod
    def require_permission(user: User, permission: str) -> None:
        """
        Raise HTTPException if user doesn't have the required permission.

        Permissions:
        - create_dataset: Create new datasets
        - edit_any_dataset: Edit any dataset
        - edit_own_dataset: Edit own datasets
        - delete_any_dataset: Delete any dataset
        - delete_own_dataset: Delete own datasets
        - view_any_dataset: View any dataset
        - view_own_dataset: View own datasets
        - manage_users: Create/edit/delete users
        - manage_system: System administration
        """
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have permission: {permission}"
            )

    @staticmethod
    def can_access_dataset(user: User, dataset: Dataset, access_type: str = "view") -> bool:
        """
        Check if user can access a dataset.

        Access types:
        - view: Read access
        - edit: Write access
        - delete: Delete access
        """
        # Admins can do anything
        if user.role == UserRole.ADMIN:
            return True

        # Check dataset visibility
        if dataset.visibility == "public":
            if access_type == "view":
                return True
            # For edit/delete, need ownership or explicit sharing
            if access_type in ["edit", "delete"] and user.has_permission(f"{access_type}_own_dataset"):
                return dataset.created_by == user.id
            return False

        # Private dataset - only creator
        if dataset.visibility == "private":
            if dataset.created_by == user.id:
                return True
            return False

        # Shared dataset - creator or explicitly shared users
        if dataset.visibility == "shared":
            if dataset.created_by == user.id:
                return True
            # Check if user is in shared_with array
            if dataset.shared_with and user.id in dataset.shared_with:
                if access_type == "view":
                    return True
                # Shared users can only view by default
                return False
            return False

        return False

    @staticmethod
    async def require_dataset_access(
        user: User,
        dataset_id: str,
        db: AsyncSession,
        access_type: str = "view"
    ) -> Dataset:
        """
        Dependency that fetches a dataset and checks access.

        Raises:
        - 400 if dataset_id is invalid UUID
        - 404 if dataset not found
        - 403 if user doesn't have access
        """
        # Validate UUID
        try:
            dataset_uuid = uuid.UUID(dataset_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid dataset ID format"
            )

        # Fetch dataset
        result = await db.execute(select(Dataset).where(Dataset.id == dataset_uuid))
        dataset = result.scalar_one_or_none()

        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found"
            )

        # Check access
        if not PermissionChecker.can_access_dataset(user, dataset, access_type):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have {access_type} access to this dataset"
            )

        return dataset


# FastAPI Dependencies

async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that requires user to be an admin."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


async def get_current_editor_or_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that requires user to be an editor or admin."""
    if user.role not in [UserRole.EDITOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor or admin access required"
        )
    return user


class DatasetAccess:
    """
    Dependency class for dataset access checking.

    Usage:
        @router.get("/{dataset_id}")
        async def get_dataset(
            dataset: Dataset = Depends(DatasetAccess("view")),
            ...
        ):
            ...
    """

    def __init__(self, access_type: str = "view"):
        """
        Args:
            access_type: Type of access required ("view", "edit", "delete")
        """
        self.access_type = access_type

    async def __call__(
        self,
        dataset_id: str,
        db: AsyncSession,
        user: User = Depends(get_current_user)
    ) -> Dataset:
        """Fetch and validate dataset access."""
        return await PermissionChecker.require_dataset_access(
            user, dataset_id, db, self.access_type
        )


# Helper for checking permissions in route handlers
def require_role(required_role: UserRole):
    """
    Factory function that creates a dependency requiring a specific role.

    Usage:
        @router.post("/admin-only")
        async def admin_endpoint(
            user: User = Depends(require_role(UserRole.ADMIN)),
            ...
        ):
            ...
    """
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{required_role.value} role required"
            )
        return user
    return role_checker


def require_permission(permission: str):
    """
    Factory function that creates a dependency requiring a specific permission.

    Usage:
        @router.post("/datasets")
        async def create_dataset(
            user: User = Depends(require_permission("create_dataset")),
            ...
        ):
            ...
    """
    async def permission_checker(user: User = Depends(get_current_user)) -> User:
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        return user
    return permission_checker
