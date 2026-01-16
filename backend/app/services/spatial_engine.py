import asyncio
from typing import List, Set
from app.dggal_utils import get_dggal_service
import logging

logger = logging.getLogger(__name__)

class SpatialEngine:
    def __init__(self):
        self.dgg_service = get_dggal_service()

    async def buffer(self, dggids: List[str], iterations: int = 1) -> List[str]:
        """
        Expands the set of dggids by 'iterations' steps.
        For each step, find neighbors of all current cells and add them to the set.
        """
        current_set = set(dggids)
        
        for _ in range(iterations):
            # We need to find neighbors for all cells in current_set
            # This can be slow if done sequentially.
            # We'll use a simple loop for now, optimization comes later.
            
            next_set = set(current_set)
            
            # To optimize, we should run these in parallel or batch if CLI supports it
            # For now, let's just do it sequentially or with simple gather 
            # effectively 'get_neighbors' is sync, so we wrap it
            
            # Helper to run sync dgg call in thread pool
            async def fetch_neighbors(did):
                return await asyncio.to_thread(self.dgg_service.get_neighbors, did)

            tasks = [fetch_neighbors(dggid) for dggid in current_set]
            results = await asyncio.gather(*tasks)
            
            for neighbors in results:
                next_set.update(neighbors)
            
            current_set = next_set
            
        return list(current_set)

    async def aggregate(self, dggids: List[str]) -> List[str]:
        """
        Converts each dggid to its parent. 
        Note: This effectively coarsens the data by one level.
        To go multiple levels, call multiple times or implement target_level logic.
        """
        parents = set()
        
        async def fetch_parent(did):
            return await asyncio.to_thread(self.dgg_service.get_parent, did)

        tasks = [fetch_parent(dggid) for dggid in dggids]
        results = await asyncio.gather(*tasks)
        
        for p in results:
            if p:
                parents.add(p)
                
        return list(parents)

    async def expand(self, dggids: List[str], iterations: int = 1) -> List[str]:
        """
        Expands dggids to their children (finer resolution).
        """
        current_set = set(dggids)
        
        for _ in range(iterations):
            next_set = set()
            
            async def fetch_children(did):
                # dgg service get_children returns list
                return await asyncio.to_thread(self.dgg_service.get_children, did)

            tasks = [fetch_children(dggid) for dggid in current_set]
            results = await asyncio.gather(*tasks)
            
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
