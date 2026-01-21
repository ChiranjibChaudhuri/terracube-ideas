import asyncio
import logging
import random
import math
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.user_repo import UserRepository
from app.dggal_utils import get_dggal_service
from app.config import settings

logger = logging.getLogger(__name__)


async def load_initial_data(session: AsyncSession):
    """
    Loads comprehensive demo data for DGGS analytics.
    Creates multiple vector and raster datasets at various resolutions.
    """
    logger.info("Checking for initial demo data...")
    
    # 1. Get Admin User
    user_repo = UserRepository(session)
    admin = await user_repo.get_by_email(settings.ADMIN_EMAIL)
    if not admin:
        logger.warning("Admin user not found, skipping data load. (Seed likely running async)")
        return

    dataset_repo = DatasetRepository(session)
    dgg_service = get_dggal_service()

    # =========================================================================
    # DATASET 1: Global Regions (Vector - Level 2)
    # =========================================================================
    await create_vector_dataset(
        session, dataset_repo, dgg_service, admin.id,
        name="Global Regions (Lv2)",
        description="Simulated global administrative regions at DGGS Level 2",
        level=2,
        bbox=[-70, -140, 70, 140],  # Most of the world
        attr_key="region",
        class_values=["region_a", "region_b", "region_c"],
        class_weights=[0.4, 0.35, 0.25]
    )

    # =========================================================================
    # DATASET 2: Protected Areas (Vector - Level 3)
    # =========================================================================
    await create_vector_dataset(
        session, dataset_repo, dgg_service, admin.id,
        name="Protected Areas (Lv3)",
        description="Simulated protected natural areas at DGGS Level 3",
        level=3,
        bbox=[20, -130, 55, -60],  # North America focus
        attr_key="protection_class",
        class_values=["national_park", "wildlife_reserve", "marine_protected"],
        class_weights=[0.5, 0.3, 0.2]
    )

    # =========================================================================
    # DATASET 3: Ocean Bathymetry (Raster - Level 4 - Global)
    # =========================================================================
    await create_raster_dataset(
        session, dataset_repo, dgg_service, admin.id,
        name="Ocean Bathymetry (Lv4)",
        description="Simulated ocean depth values (inspired by GEBCO)",
        level=4,
        bbox=[-75, -180, 75, 180],  # Global oceans
        attr_key="depth",
        value_range=(-8000, 0),  # Depth in meters (negative = below sea level)
        apply_geographic_pattern=True,
        pattern_type="ocean_depth"
    )

    # =========================================================================
    # DATASET 4: Temperature (Raster - Level 4 - Global)
    # =========================================================================
    await create_raster_dataset(
        session, dataset_repo, dgg_service, admin.id,
        name="Global Temperature (Lv4)",
        description="Simulated annual mean temperature",
        level=4,
        bbox=[-80, -180, 80, 180],  # Near-global coverage
        attr_key="temp_celsius",
        value_range=(-30, 45),
        apply_geographic_pattern=True,
        pattern_type="temperature"
    )

    # =========================================================================
    # DATASET 5: Elevation (Raster - Level 4 - Global)
    # =========================================================================
    await create_raster_dataset(
        session, dataset_repo, dgg_service, admin.id,
        name="Global Elevation (Lv4)",
        description="Simulated global terrain elevation",
        level=4,
        bbox=[-70, -180, 70, 180],  # Global land coverage
        attr_key="elevation",
        value_range=(0, 4500),  # Elevation in meters
        apply_geographic_pattern=True,
        pattern_type="elevation"
    )

    # =========================================================================
    # DATASET 6: North America Climate (Regional - Level 5)
    # =========================================================================
    await create_raster_dataset(
        session, dataset_repo, dgg_service, admin.id,
        name="North America Climate (Lv5)",
        description="Regional temperature data for North America",
        level=5,
        bbox=[24, -130, 55, -65],  # Continental US + Canada
        attr_key="temp_celsius",
        value_range=(-20, 35),
        apply_geographic_pattern=True,
        pattern_type="temperature"
    )

    # =========================================================================
    # DATASET 7: Europe Climate (Regional - Level 5)
    # =========================================================================
    await create_raster_dataset(
        session, dataset_repo, dgg_service, admin.id,
        name="Europe Climate (Lv5)",
        description="Regional temperature data for Europe",
        level=5,
        bbox=[35, -10, 70, 40],  # Western/Central Europe
        attr_key="temp_celsius",
        value_range=(-10, 30),
        apply_geographic_pattern=True,
        pattern_type="temperature"
    )

    # =========================================================================
    # DATASET 8: South America Elevation (Regional - Level 5)
    # =========================================================================
    await create_raster_dataset(
        session, dataset_repo, dgg_service, admin.id,
        name="South America Elevation (Lv5)",
        description="Regional terrain elevation for South America (Andes focus)",
        level=5,
        bbox=[-55, -80, 12, -35],  # South America
        attr_key="elevation",
        value_range=(0, 6500),  # Higher for Andes mountains
        apply_geographic_pattern=True,
        pattern_type="elevation"
    )

    logger.info("Demo data loading complete.")


async def create_vector_dataset(
    session: AsyncSession,
    dataset_repo: DatasetRepository,
    dgg_service,
    admin_id,
    name: str,
    description: str,
    level: int,
    bbox: list,
    attr_key: str,
    class_values: list,
    class_weights: list
):
    """Create a vector-type dataset with categorical values."""
    existing = await session.execute(
        text("SELECT id FROM datasets WHERE name = :name"), {"name": name}
    )
    if existing.scalar():
        logger.info(f"Dataset '{name}' already exists, skipping.")
        return

    logger.info(f"Creating dataset: {name}...")
    
    dataset = await dataset_repo.create(
        name=name,
        description=description,
        dggs_name="IVEA3H",
        level=level,
        created_by=admin_id,
        metadata_={
            "attr_key": attr_key,
            "min_level": level,
            "max_level": level,
            "source_type": "vector",
            "class_values": class_values,
        }
    )

    try:
        cells = await asyncio.to_thread(dgg_service.list_zones_bbox, level, bbox)
        if not cells:
            logger.warning(f"No cells generated for {name}")
            return

        # Create partition table for this dataset
        partition_table = f"cell_objects_{str(dataset.id).replace('-', '_')}"
        
        # Insert with weighted random class assignment
        values = []
        for cid in cells:
            class_val = random.choices(class_values, weights=class_weights, k=1)[0]
            # Escape single quotes in class values
            safe_val = class_val.replace("'", "''")
            values.append(f"('{dataset.id}', '{cid}', 0, '{attr_key}', '{safe_val}')")

        await bulk_insert(session, partition_table, values, is_text=True)
        logger.info(f"Loaded {len(cells)} cells into '{name}'")

    except Exception as e:
        logger.error(f"Failed to load vector data for {name}: {e}")
        await session.rollback()


async def create_raster_dataset(
    session: AsyncSession,
    dataset_repo: DatasetRepository,
    dgg_service,
    admin_id,
    name: str,
    description: str,
    level: int,
    bbox: list,
    attr_key: str,
    value_range: tuple,
    apply_geographic_pattern: bool = False,
    pattern_type: str = "random"
):
    """Create a raster-type dataset with numeric values."""
    existing = await session.execute(
        text("SELECT id FROM datasets WHERE name = :name"), {"name": name}
    )
    if existing.scalar():
        logger.info(f"Dataset '{name}' already exists, skipping.")
        return

    logger.info(f"Creating dataset: {name}...")
    
    min_val, max_val = value_range
    
    dataset = await dataset_repo.create(
        name=name,
        description=description,
        dggs_name="IVEA3H",
        level=level,
        created_by=admin_id,
        metadata_={
            "attr_key": attr_key,
            "min_level": level,
            "max_level": level,
            "source_type": "raster",
            "min_value": min_val,
            "max_value": max_val,
        }
    )

    try:
        cells = await asyncio.to_thread(dgg_service.list_zones_bbox, level, bbox)
        if not cells:
            logger.warning(f"No cells generated for {name}")
            return

        partition_table = f"cell_objects_{str(dataset.id).replace('-', '_')}"
        
        values = []
        for i, cid in enumerate(cells):
            if apply_geographic_pattern:
                value = generate_patterned_value(i, len(cells), min_val, max_val, pattern_type)
            else:
                value = round(random.uniform(min_val, max_val), 2)
            values.append(f"('{dataset.id}', '{cid}', 0, '{attr_key}', {value})")

        await bulk_insert(session, partition_table, values, is_text=False)
        logger.info(f"Loaded {len(cells)} cells into '{name}'")

    except Exception as e:
        logger.error(f"Failed to load raster data for {name}: {e}")
        await session.rollback()


def generate_patterned_value(index: int, total: int, min_val: float, max_val: float, pattern_type: str) -> float:
    """Generate values with geographic-like patterns."""
    t = index / max(total - 1, 1)  # Normalized position [0, 1]
    
    if pattern_type == "temperature":
        # Higher at center (equator), lower at edges (poles)
        lat_factor = 1 - abs(2 * t - 1)  # Peak at center
        base = min_val + (max_val - min_val) * lat_factor
        noise = random.uniform(-5, 5)
        return round(max(min_val, min(max_val, base + noise)), 1)
    
    elif pattern_type == "ocean_depth":
        # Variable depth with some deep trenches
        depth = random.gauss(-3000, 1500)
        if random.random() < 0.05:  # 5% chance of deep trench
            depth = random.uniform(-8000, -6000)
        elif random.random() < 0.15:  # 15% shallow/coastal
            depth = random.uniform(-200, 0)
        return round(max(min_val, min(max_val, depth)), 0)
    
    elif pattern_type == "elevation":
        # Varied terrain with occasional mountains
        base = random.gauss(500, 400)
        if random.random() < 0.1:  # 10% mountains
            base = random.uniform(2000, 4500)
        elif random.random() < 0.2:  # 20% lowlands
            base = random.uniform(0, 200)
        return round(max(min_val, min(max_val, base)), 0)
    
    else:
        # Random distribution
        return round(random.uniform(min_val, max_val), 2)


async def bulk_insert(session: AsyncSession, partition_table: str, values: list, is_text: bool):
    """Perform chunked bulk insert into partition table."""
    if not values:
        return
    
    chunk_size = 500
    value_col = "value_text" if is_text else "value_num"
    
    for i in range(0, len(values), chunk_size):
        chunk = values[i:i + chunk_size]
        sql = f"""
            INSERT INTO "{partition_table}" (dataset_id, dggid, tid, attr_key, {value_col})
            VALUES {",".join(chunk)}
        """
        await session.execute(text(sql))
    
    await session.commit()
