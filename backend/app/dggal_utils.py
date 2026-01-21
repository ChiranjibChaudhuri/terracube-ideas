from functools import lru_cache
from typing import Optional, List, Dict, Any, Callable
import logging
import threading
from dggal import Application, pydggal_setup, GeoExtent, GeoPoint, Array, nullZone
from dggal import IVEA3H, ISEA3H, IVEA7H, ISEA7H

logger = logging.getLogger("uvicorn.error")

_dggal_app = None
def _init_dggal():
    global _dggal_app
    if _dggal_app is None:
        _dggal_app = Application(appGlobals=globals())
        pydggal_setup(_dggal_app)
    return _dggal_app

DGGRS_CLASS_MAP: Dict[str, Callable[[], Any]] = {
    "IVEA3H": IVEA3H,
    "ISEA3H": ISEA3H,
    "IVEA7H": IVEA7H,
    "ISEA7H": ISEA7H,
}

class DggalService:
    def __init__(self, system_name: str = "IVEA3H"):
        _init_dggal()
        self.system_name = system_name.upper()
        dggrs_class = DGGRS_CLASS_MAP.get(self.system_name)
        if not dggrs_class:
            logger.warning(f"Unknown DGGRS '{system_name}', defaulting to IVEA3H.")
            dggrs_class = IVEA3H
        self.dggrs = dggrs_class()
        self._lock = threading.Lock()

    def _zone_from_text(self, dggid: str):
        zone = self.dggrs.getZoneFromTextID(dggid)
        if zone == nullZone:
            return None
        return zone

    def get_neighbors(self, dggid: str) -> List[str]:
        with self._lock:
            zone = self._zone_from_text(dggid)
            if zone is None:
                return []
            nb_types = Array("<int>")
            neighbors = self.dggrs.getZoneNeighbors(zone, nb_types)
            if not neighbors:
                return []
            return [self.dggrs.getZoneTextID(nb) for nb in neighbors]

    def get_parent(self, dggid: str) -> Optional[str]:
        with self._lock:
            zone = self._zone_from_text(dggid)
            if zone is None:
                return None
            parents = self.dggrs.getZoneParents(zone)
            if not parents or parents.count == 0:
                return None
            return self.dggrs.getZoneTextID(parents[0])

    def get_children(self, dggid: str) -> List[str]:
        with self._lock:
            zone = self._zone_from_text(dggid)
            if zone is None:
                return []
            children = self.dggrs.getZoneChildren(zone)
            if not children:
                return []
            return [self.dggrs.getZoneTextID(child) for child in children]

    def get_vertices(self, dggid: str, refinement: int = 3) -> List[Dict[str, float]]:
        with self._lock:
            zone = self._zone_from_text(dggid)
            if zone is None:
                return []
            vertices = self.dggrs.getZoneRefinedWGS84Vertices(zone, refinement)
            if not vertices:
                return []
            return [{"lat": float(v.lat), "lon": float(v.lon)} for v in vertices]

    def list_zones_bbox(self, level: int, bbox: List[float]) -> List[str]:
        with self._lock:
            extent = GeoExtent()
            extent.ll = GeoPoint(lat=bbox[0], lon=bbox[1])
            extent.ur = GeoPoint(lat=bbox[2], lon=bbox[3])
            zones = self.dggrs.listZones(level, extent)
            if not zones:
                return []
            return [self.dggrs.getZoneTextID(zone) for zone in zones]

    def get_centroid(self, dggid: str) -> Dict[str, float]:
        with self._lock:
            zone = self._zone_from_text(dggid)
            if zone is None:
                return {"lat": 0.0, "lon": 0.0}
            centroid = self.dggrs.getZoneWGS84Centroid(zone)
            return {"lat": float(centroid.lat), "lon": float(centroid.lon)}

    def get_zone_level(self, dggid: str) -> Optional[int]:
        """Get the resolution level of a DGGS zone."""
        with self._lock:
            zone = self._zone_from_text(dggid)
            if zone is None:
                return None
            return self.dggrs.getZoneLevel(zone)

    def get_parent_at_level(self, dggid: str, target_level: int) -> Optional[str]:
        """Get the ancestor of a zone at a specific level."""
        with self._lock:
            zone = self._zone_from_text(dggid)
            if zone is None:
                return None
            current_level = self.dggrs.getZoneLevel(zone)
            if current_level is None or current_level <= target_level:
                return dggid  # Already at or above target level
            
            # Traverse up the hierarchy
            current = zone
            while current_level > target_level:
                parents = self.dggrs.getZoneParents(current)
                if not parents or parents.count == 0:
                    return None
                current = parents[0]
                current_level = self.dggrs.getZoneLevel(current)
            
            return self.dggrs.getZoneTextID(current)

@lru_cache
def get_dggal_service(system_name: str = "IVEA3H") -> DggalService:
    return DggalService(system_name)
