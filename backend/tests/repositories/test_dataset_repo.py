"""
Unit tests for DatasetRepository.
"""
import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.repositories.dataset_repo import DatasetRepository
from app.models import Dataset


@pytest.mark.asyncio
async def test_create_dataset(db_session: AsyncSession):
    """Test creating a new dataset."""
    repo = DatasetRepository(db_session)

    dataset = await repo.create(
        name="Test Dataset",
        description="Test description",
        level=10,
        dggs_name="IVEA3H"
    )

    assert dataset.id is not None
    assert dataset.name == "Test Dataset"
    assert dataset.level == 10
    assert dataset.dggs_name == "IVEA3H"
    assert dataset.status == "active"


@pytest.mark.asyncio
async def test_get_by_id(db_session: AsyncSession):
    """Test retrieving a dataset by ID."""
    repo = DatasetRepository(db_session)

    # Create a dataset first
    dataset = await repo.create(name="Test Dataset")
    dataset_id = dataset.id

    # Retrieve it
    retrieved = await repo.get_by_id(dataset_id)

    assert retrieved is not None
    assert retrieved.id == dataset_id
    assert retrieved.name == "Test Dataset"


@pytest.mark.asyncio
async def test_get_by_id_not_found(db_session: AsyncSession):
    """Test retrieving non-existent dataset returns None."""
    repo = DatasetRepository(db_session)

    # Use a random UUID that shouldn't exist
    fake_id = uuid.uuid4()
    result = await repo.get_by_id(fake_id)

    assert result is None


@pytest.mark.asyncio
async def test_list_datasets(db_session: AsyncSession):
    """Test listing all datasets."""
    repo = DatasetRepository(db_session)

    # Create multiple datasets
    await repo.create(name="Dataset A")
    await repo.create(name="Dataset B")
    await repo.create(name="Dataset C")

    # List all
    datasets = await repo.list_all()

    assert len(datasets) >= 3
    names = [d.name for d in datasets]
    assert "Dataset A" in names
    assert "Dataset B" in names
    assert "Dataset C" in names


@pytest.mark.asyncio
async def test_update_dataset(db_session: AsyncSession):
    """Test updating a dataset."""
    repo = DatasetRepository(db_session)

    # Create a dataset
    dataset = await repo.create(name="Original Name")
    dataset_id = dataset.id

    # Update it
    updated = await repo.update(
        dataset_id,
        name="Updated Name",
        description="Updated description"
    )

    assert updated.id == dataset_id
    assert updated.name == "Updated Name"
    assert updated.description == "Updated description"


@pytest.mark.asyncio
async def test_delete_dataset(db_session: AsyncSession):
    """Test deleting a dataset."""
    repo = DatasetRepository(db_session)

    # Create a dataset
    dataset = await repo.create(name="To Delete")
    dataset_id = dataset.id

    # Delete it
    await repo.delete(dataset_id)

    # Verify it's gone
    result = await repo.get_by_id(dataset_id)
    assert result is None


@pytest.mark.asyncio
async def test_dataset_exists(db_session: AsyncSession):
    """Test checking if a dataset exists."""
    repo = DatasetRepository(db_session)

    # Non-existent dataset
    fake_id = uuid.uuid4()
    assert await repo.exists(fake_id) is False

    # Create and check exists
    dataset = await repo.create(name="Exists Test")
    assert await repo.exists(dataset.id) is True
