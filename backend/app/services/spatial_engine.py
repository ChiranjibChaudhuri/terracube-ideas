import asyncio
from typing import List, Set
from app.dggal_utils import get_dggal_service
import logging

logger = logging.getLogger(__name__)

class SpatialEngine:
    def __init__(self, dggs_name: str = "IVEA3H"):
        self.dgg_service = get_dggal_service(dggs_name)
        self.max_concurrency = 32

    async def _gather_limited(self, func, items, limit: int):
        if not items:
            return []
        semaphore = asyncio.Semaphore(limit)

        async def run(item):
            async with semaphore:
                return await asyncio.to_thread(func, item)

        results = []
        batch_size = max(limit * 4, 1)
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            results.extend(await asyncio.gather(*(run(item) for item in batch)))
        return results

    async def buffer(self, dggids: List[str], iterations: int = 1, max_cells: int = 50000) -> List[str]:
        """
        Expands the set of dggids by 'iterations' steps.
        For each step, find neighbors of all current cells and add them to the set.
        Stops early if max_cells limit is reached to prevent memory exhaustion.
        """
        current_set = set(dggids)
        
        for i in range(iterations):
            if len(current_set) > max_cells:
                logger.warning(f"Buffer hit limit at iteration {i}: {len(current_set)} > {max_cells}")
                break
            
            next_set = set(current_set)
            
            results = await self._gather_limited(
                self.dgg_service.get_neighbors,
                list(current_set),
                self.max_concurrency,
            )
            
            for neighbors in results:
                next_set.update(neighbors)
            
            current_set = next_set
            
        return list(current_set)[:max_cells]

    async def aggregate(self, dggids: List[str], levels: int = 1) -> List[str]:
        """
        Converts each dggid to its parent, optionally multiple levels.
        This effectively coarsens the data by 'levels' steps.
        """
        current = set(dggids)
        
        for _ in range(levels):
            results = await self._gather_limited(
                self.dgg_service.get_parent,
                list(current),
                self.max_concurrency,
            )
            current = {p for p in results if p}
                
        return list(current)

    async def expand(self, dggids: List[str], iterations: int = 1) -> List[str]:
        """
        Expands dggids to their children (finer resolution).
        """
        current_set = set(dggids)
        
        for _ in range(iterations):
            next_set = set()
            
            results = await self._gather_limited(
                self.dgg_service.get_children,
                list(current_set),
                self.max_concurrency,
            )
            
            for children in results:
                if children:
                    next_set.update(children)
            
            current_set = next_set
            
        return list(current_set)

    # Set operations on DGGID lists
    def union(self, list_a: List[str], list_b: List[str]) -> List[str]:
        return list(set(list_a).union(set(list_b)))

    def intersection(self, list_a: List[str], list_b: List[str]) -> List[str]:
        return list(set(list_a).intersection(set(list_b)))

    def difference(self, list_a: List[str], list_b: List[str]) -> List[str]:
        """Returns A - B"""
        return list(set(list_a).difference(set(list_b)))

    # Masking is effectively intersection
    def mask(self, source_dggids: List[str], mask_dggids: List[str]) -> List[str]:
        return self.intersection(source_dggids, mask_dggids)
