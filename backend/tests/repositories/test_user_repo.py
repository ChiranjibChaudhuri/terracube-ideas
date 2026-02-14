"""
Unit tests for UserRepository.
"""
import pytest
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.repositories.user_repo import UserRepository
from app.models import User


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    """Test creating a new user."""
    repo = UserRepository(db_session)

    user = await repo.create(
        email="test@example.com",
        password_hash="hashed_password_here",
        name="Test User"
    )

    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.name == "Test User"
    assert user.role == "viewer"  # default role


@pytest.mark.asyncio
async def test_get_by_id(db_session: AsyncSession):
    """Test retrieving a user by ID."""
    repo = UserRepository(db_session)

    # Create a user first
    user = await repo.create(
        email="id_lookup@example.com",
        password_hash="hashed",
        name="ID Lookup User"
    )

    # Retrieve it
    retrieved = await repo.get_by_id(user.id)

    assert retrieved is not None
    assert retrieved.id == user.id
    assert retrieved.email == user.email


@pytest.mark.asyncio
async def test_get_by_email(db_session: AsyncSession):
    """Test retrieving a user by email."""
    repo = UserRepository(db_session)

    # Create a user
    user = await repo.create(
        email="email@example.com",
        password_hash="hashed",
        name="Email User"
    )

    # Retrieve by email
    retrieved = await repo.get_by_email("email@example.com")

    assert retrieved is not None
    assert retrieved.id == user.id


@pytest.mark.asyncio
async def test_get_by_email_not_found(db_session: AsyncSession):
    """Test retrieving non-existent user by email."""
    repo = UserRepository(db_session)

    result = await repo.get_by_email("notfound@example.com")

    assert result is None
