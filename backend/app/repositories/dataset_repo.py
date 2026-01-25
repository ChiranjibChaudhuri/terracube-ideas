from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models import Dataset

from sqlalchemy import text
import uuid

class DatasetRepository(BaseRepository[Dataset]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Dataset)
    
    async def create(self, **kwargs) -> Dataset:
        # Create the dataset record
        dataset = await super().create(**kwargs)
        
        # Create a partition for this dataset features
        # Partition name convention: cell_objects_<clean_uuid>
        ds_id_str = str(dataset.id)
        
        # Verify UUID format to prevent any SQL injection risk
        try:
            uuid.UUID(ds_id_str)
        except ValueError:
            raise ValueError(f"Invalid UUID for dataset ID: {ds_id_str}")

        clean_uuid = ds_id_str.replace('-', '_')
        partition_name = f"cell_objects_{clean_uuid}"

        # Safe interpolation because ID is strictly validated as UUID
        sql = f"""
            CREATE TABLE IF NOT EXISTS "{partition_name}" 
            PARTITION OF cell_objects 
            FOR VALUES IN ('{ds_id_str}')
        """
        await self.session.execute(text(sql))
        await self.session.commit()
        
        return dataset
