from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, intersect, union, except_, literal_column
from typing import List, Optional
from app.repositories.base import BaseRepository
from app.models import CellObject
import uuid

class CellObjectRepository(BaseRepository[CellObject]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, CellObject)

    async def execute_set_operation(self, operation: str, dataset_ids: List[str], dggid_filter: Optional[List[str]] = None, limit: int = 1000):
        if not dataset_ids:
            return []
            
        selects = []
        for ds_id in dataset_ids:
            # Cast ds_id string to UUID if needed, but SQLAlchemy handles it if model is UUID
            stmt = select(CellObject.dggid).where(CellObject.dataset_id == uuid.UUID(ds_id))
            if dggid_filter:
                 stmt = stmt.where(CellObject.dggid.in_(dggid_filter))
            selects.append(stmt)
            
        final_stmt = None
        if operation == "intersection":
            final_stmt = intersect(*selects)
        elif operation == "union":
            final_stmt = union(*selects)
        elif operation == "difference":
            # Difference is usually A - B - C ...
            final_stmt = except_(*selects)
        else:
            raise ValueError(f"Unknown operation: {operation}")
            
        # Add limit
        final_stmt = final_stmt.limit(limit)
        
        result = await self.session.execute(final_stmt)
        return list(result.scalars().all())

    async def get_values_by_dggids(self, dataset_id: str, dggids: List[str]) -> List[float]:
        """Fetch numeric values for a set of dggids in a dataset."""
        if not dggids:
            return []
            
        stmt = select(CellObject.value_num).where(
            CellObject.dataset_id == uuid.UUID(dataset_id),
            CellObject.dggid.in_(dggids),
            CellObject.value_num.isnot(None)
        )
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
