from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.dggal_utils import get_dggal_service
from app.models import CellObject
import uuid
import logging

logger = logging.getLogger(__name__)

class HighVibeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.dggal = get_dggal_service()

    async def get_zone_data(self, zone_id: str, depth: int, dataset_id: str, attr_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieves data for a zone and its subzones at a specific depth in the High Vibes format.
        """
        # 1. Get DGGIDs for the requested depth
        if depth == 0:
            dggids = [zone_id]
        else:
            dggids = self.dggal.get_subzones(zone_id, depth)

        if not dggids:
             return {"zoneId": zone_id, "values": {}}

        # 2. Fetch data from database
        try:
            stmt = select(CellObject.dggid, CellObject.value_num).where(
                CellObject.dataset_id == uuid.UUID(dataset_id),
                CellObject.dggid.in_(dggids)
            )
            if attr_key:
                stmt = stmt.where(CellObject.attr_key == attr_key)

            result = await self.db.execute(stmt)
            data_map = {row[0]: row[1] for row in result.all()}
        except Exception as e:
            logger.error(f"Error fetching data for high vibes: {e}")
            data_map = {}

        # 3. Order data according to dggids list (which comes from dggal subzones order)
        # Missing values are None
        ordered_data = [data_map.get(did) for did in dggids]

        # 4. Construct response
        key_name = attr_key or "value"
        return {
            "zoneId": zone_id,
            "values": {
                key_name: [
                    {
                        "depth": depth,
                        "shape": {
                            "count": len(ordered_data)
                        },
                        "data": ordered_data,
                        "ids": dggids
                    }
                ]
            }
        }
