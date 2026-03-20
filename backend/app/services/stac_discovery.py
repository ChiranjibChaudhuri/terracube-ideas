"""STAC Discovery Service: search STAC catalogs and return scene metadata."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pystac_client import Client as StacClient

logger = logging.getLogger(__name__)

try:
    import planetary_computer
except ImportError:  # pragma: no cover - optional dependency
    planetary_computer = None

# Band mappings for common STAC collections
BAND_MAPS: Dict[str, Dict[str, str]] = {
    "sentinel-2-l2a": {
        "B02": "blue", "B03": "green", "B04": "red", "B05": "rededge1",
        "B06": "rededge2", "B07": "rededge3", "B08": "nir", "B8A": "nir08",
        "B11": "swir16", "B12": "swir22", "SCL": "scl",
    },
    "landsat-c2-l2": {
        "B1": "coastal", "B2": "blue", "B3": "green", "B4": "red",
        "B5": "nir08", "B6": "swir16", "B7": "swir22", "ST_B10": "lwir11",
    },
    "cop-dem-glo-30": {"elevation": "data"},
    "cop-dem-glo-90": {"elevation": "data"},
    "alos-dem": {"elevation": "data"},
    "esa-worldcover": {"map": "map"},
    "naip": {"R": "image", "G": "image", "B": "image", "NIR": "image"},
}


class StacDiscovery:
    """Search STAC catalogs and discover satellite scenes."""

    def search(
        self,
        api_url: str,
        collection: str,
        auth_type: Optional[str] = None,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        date_range: Optional[Tuple[str, str]] = None,
        cloud_cover_lt: Optional[float] = None,
        max_items: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search a STAC API and return scene metadata.

        Args:
            api_url: STAC API root URL
            collection: STAC collection ID (e.g. "sentinel-2-l2a")
            bbox: (west, south, east, north) in WGS84
            date_range: ("YYYY-MM-DD", "YYYY-MM-DD")
            cloud_cover_lt: Max cloud cover percentage
            max_items: Maximum scenes to return

        Returns:
            List of scene dicts with id, bbox, datetime, cloud_cover, bands, thumbnail, properties
        """
        logger.info(
            "STAC search: collection=%s bbox=%s dates=%s cloud<%s max=%d",
            collection, bbox, date_range, cloud_cover_lt, max_items,
        )

        search_params: Dict[str, Any] = {
            "collections": [collection],
            "limit": min(max_items, 250),
            "max_items": max_items,
        }
        if bbox:
            search_params["bbox"] = list(bbox)
        if date_range:
            search_params["datetime"] = f"{date_range[0]}/{date_range[1]}"

        # Build query filter for cloud cover
        if cloud_cover_lt is not None:
            search_params["query"] = {"eo:cloud_cover": {"lt": cloud_cover_lt}}

        client = self._open_client(api_url, auth_type)
        search = client.search(**search_params)

        scenes = []
        for item in search.items_as_dicts():
            scene = self._extract_scene(item, collection)
            scenes.append(scene)
            if len(scenes) >= max_items:
                break

        logger.info("STAC search returned %d scenes", len(scenes))
        return scenes

    def _open_client(self, api_url: str, auth_type: Optional[str] = None) -> StacClient:
        """Open a STAC client with any catalog-specific asset modifier."""
        modifier = None

        if auth_type == "planetary_computer":
            if planetary_computer is None:
                logger.warning(
                    "planetary-computer package is not installed; proceeding without asset signing"
                )
            else:
                modifier = planetary_computer.sign_inplace

        if modifier is not None:
            return StacClient.open(api_url, modifier=modifier)

        return StacClient.open(api_url)

    def _extract_scene(self, item: Dict[str, Any], collection: str) -> Dict[str, Any]:
        """Extract normalized scene metadata from a STAC item dict."""
        props = item.get("properties", {})
        assets = item.get("assets", {})

        # Extract band info using band map or all assets
        band_map = BAND_MAPS.get(collection, {})
        bands: Dict[str, Dict[str, Any]] = {}

        if band_map:
            # Use configured band mapping
            for band_name, asset_key in band_map.items():
                if asset_key in assets:
                    asset = assets[asset_key]
                    bands[band_name] = {
                        "href": asset.get("href", ""),
                        "type": asset.get("type", ""),
                    }
        else:
            # Auto-discover bands from assets with raster extensions
            for key, asset in assets.items():
                asset_type = asset.get("type", "")
                roles = asset.get("roles", [])
                if "image/tiff" in asset_type or "data" in roles:
                    bands[key] = {
                        "href": asset.get("href", ""),
                        "type": asset_type,
                    }

        # Find thumbnail
        thumbnail_url = None
        for key in ("thumbnail", "rendered_preview", "preview"):
            if key in assets:
                thumbnail_url = assets[key].get("href")
                break

        # Parse datetime
        dt_str = props.get("datetime")
        dt_parsed = None
        if dt_str:
            try:
                if dt_str.endswith("Z"):
                    dt_str = dt_str[:-1] + "+00:00"
                dt_parsed = datetime.fromisoformat(dt_str).isoformat()
            except (ValueError, TypeError):
                dt_parsed = dt_str

        return {
            "stac_item_id": item["id"],
            "collection": item.get("collection", collection),
            "bbox": item.get("bbox"),
            "datetime": dt_parsed,
            "cloud_cover": props.get("eo:cloud_cover"),
            "bands": bands,
            "thumbnail_url": thumbnail_url,
            "properties": {
                "platform": props.get("platform"),
                "instrument": props.get("instruments"),
                "gsd": props.get("gsd"),
                "constellation": props.get("constellation"),
                "view:off_nadir": props.get("view:off_nadir"),
                "created": props.get("created"),
            },
        }

    def get_available_bands(
        self,
        collection: str,
        scenes: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Return available band names for a STAC collection or scene set."""
        band_map = BAND_MAPS.get(collection, {})
        if band_map:
            return list(band_map.keys())

        ordered_bands: List[str] = []
        seen = set()
        for scene in scenes or []:
            for band_name in (scene.get("bands") or {}).keys():
                if band_name in seen:
                    continue
                seen.add(band_name)
                ordered_bands.append(band_name)

        return ordered_bands
