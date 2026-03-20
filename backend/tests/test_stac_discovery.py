from app.services.stac_discovery import StacDiscovery


def test_get_available_bands_prefers_known_collection_map():
    discovery = StacDiscovery()

    bands = discovery.get_available_bands(
        "sentinel-2-l2a",
        scenes=[{"bands": {"custom": {"href": "ignored"}}}],
    )

    assert bands[:4] == ["B02", "B03", "B04", "B05"]


def test_get_available_bands_unions_scene_bands_for_unknown_collection():
    discovery = StacDiscovery()

    bands = discovery.get_available_bands(
        "sentinel-1-grd",
        scenes=[
            {"bands": {"vv": {"href": "a"}, "vh": {"href": "b"}}},
            {"bands": {"vh": {"href": "c"}, "hh": {"href": "d"}}},
        ],
    )

    assert bands == ["vv", "vh", "hh"]


def test_extract_scene_auto_discovers_raster_assets():
    discovery = StacDiscovery()
    item = {
        "id": "worldcover-scene",
        "collection": "esa-worldcover",
        "bbox": [-10.0, -10.0, 10.0, 10.0],
        "properties": {"datetime": "2026-03-18T00:00:00Z"},
        "assets": {
            "map": {
                "href": "https://example.com/worldcover.tif",
                "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                "roles": ["data"],
            },
            "rendered_preview": {
                "href": "https://example.com/preview.png",
                "type": "image/png",
            },
        },
    }

    scene = discovery._extract_scene(item, "esa-worldcover")

    assert scene["bands"] == {
        "map": {
            "href": "https://example.com/worldcover.tif",
            "type": "image/tiff; application=geotiff; profile=cloud-optimized",
        }
    }
    assert scene["thumbnail_url"] == "https://example.com/preview.png"
    assert scene["datetime"] == "2026-03-18T00:00:00+00:00"
