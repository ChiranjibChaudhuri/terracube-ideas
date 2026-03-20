"""Align Alembic-managed databases with the repaired runtime schema.

Revision ID: 002
Revises: 001
Create Date: 2026-03-16
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    """Bring older Alembic databases up to the current runtime schema."""
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # Repair the old non-partitioned cell_objects_default table from the original 001 migration.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.cell_objects') IS NULL THEN
                IF to_regclass('public.cell_objects_default') IS NOT NULL THEN
                    ALTER TABLE cell_objects_default RENAME TO cell_objects_legacy_default;
                END IF;

                EXECUTE '
                    CREATE TABLE cell_objects (
                      id bigserial,
                      dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
                      dggid text NOT NULL,
                      tid integer NOT NULL,
                      attr_key text NOT NULL,
                      value_text text,
                      value_num double precision,
                      value_json jsonb,
                      created_at timestamptz NOT NULL DEFAULT now(),
                      PRIMARY KEY (id, dataset_id),
                      UNIQUE (dataset_id, dggid, tid, attr_key)
                    ) PARTITION BY LIST (dataset_id)
                ';

                EXECUTE 'CREATE TABLE cell_objects_default PARTITION OF cell_objects DEFAULT';

                IF to_regclass('public.cell_objects_legacy_default') IS NOT NULL THEN
                    EXECUTE '
                        INSERT INTO cell_objects_default (
                            id, dataset_id, dggid, tid, attr_key, value_text, value_num, value_json, created_at
                        )
                        SELECT id, dataset_id, dggid, tid, attr_key, value_text, value_num, value_json, created_at
                        FROM cell_objects_legacy_default
                    ';
                    EXECUTE 'DROP TABLE cell_objects_legacy_default';
                END IF;
            ELSIF to_regclass('public.cell_objects_default') IS NULL THEN
                EXECUTE 'CREATE TABLE cell_objects_default PARTITION OF cell_objects DEFAULT';
            END IF;
        END $$;
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS idx_cell_objects_dataset_id ON cell_objects (dataset_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cell_objects_dataset_dggid ON cell_objects (dataset_id, dggid)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cell_objects_dggid ON cell_objects (dggid)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cell_objects_attr_key ON cell_objects (attr_key)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cell_objects_tid ON cell_objects (tid)")

    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role text NOT NULL DEFAULT 'viewer'")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT TRUE")

    op.execute("ALTER TABLE datasets ADD COLUMN IF NOT EXISTS visibility text NOT NULL DEFAULT 'private'")
    op.execute("ALTER TABLE datasets ADD COLUMN IF NOT EXISTS shared_with uuid[] NOT NULL DEFAULT ARRAY[]::uuid[]")

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'annotations' AND column_name = 'dggid'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'annotations' AND column_name = 'cell_dggid'
            ) THEN
                ALTER TABLE annotations RENAME COLUMN dggid TO cell_dggid;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'cell_annotations' AND column_name = 'dggid'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'cell_annotations' AND column_name = 'cell_dggid'
            ) THEN
                ALTER TABLE cell_annotations RENAME COLUMN dggid TO cell_dggid;
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS annotations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          cell_dggid text NOT NULL,
          dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
          content text NOT NULL,
          annotation_type text NOT NULL DEFAULT 'note',
          visibility text NOT NULL DEFAULT 'private',
          created_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("ALTER TABLE annotations ADD COLUMN IF NOT EXISTS cell_dggid text")
    op.execute("ALTER TABLE annotations ADD COLUMN IF NOT EXISTS dataset_id uuid REFERENCES datasets(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE annotations ADD COLUMN IF NOT EXISTS annotation_type text NOT NULL DEFAULT 'note'")
    op.execute("ALTER TABLE annotations ADD COLUMN IF NOT EXISTS visibility text NOT NULL DEFAULT 'private'")
    op.execute("ALTER TABLE annotations ADD COLUMN IF NOT EXISTS created_by uuid REFERENCES users(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE annotations ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now()")
    op.execute("ALTER TABLE annotations ALTER COLUMN created_at SET DEFAULT now()")
    op.execute("ALTER TABLE annotations ALTER COLUMN updated_at SET DEFAULT now()")
    op.execute("CREATE INDEX IF NOT EXISTS idx_annotations_cell ON annotations (cell_dggid)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_annotations_dataset ON annotations (dataset_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_annotations_type ON annotations (annotation_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_annotations_visibility ON annotations (visibility)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_annotations_created_by ON annotations (created_by)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cell_annotations (
          id bigserial PRIMARY KEY,
          annotation_id uuid NOT NULL REFERENCES annotations(id) ON DELETE CASCADE,
          cell_dggid text NOT NULL
        )
        """
    )
    op.execute("ALTER TABLE cell_annotations ADD COLUMN IF NOT EXISTS cell_dggid text")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cell_annotations_annotation ON cell_annotations (annotation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cell_annotations_cell ON cell_annotations (cell_dggid)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_cell_annotations ON cell_annotations (annotation_id, cell_dggid)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS annotation_shares (
          id bigserial PRIMARY KEY,
          annotation_id uuid NOT NULL REFERENCES annotations(id) ON DELETE CASCADE,
          shared_with uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("ALTER TABLE annotation_shares ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now()")
    op.execute("CREATE INDEX IF NOT EXISTS idx_annotation_shares_annotation ON annotation_shares (annotation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_annotation_shares_user ON annotation_shares (shared_with)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_annotation_shares ON annotation_shares (annotation_id, shared_with)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS stac_catalogs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL UNIQUE,
            api_url TEXT NOT NULL,
            catalog_type TEXT NOT NULL DEFAULT 'api',
            auth_type TEXT,
            collections JSONB DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS stac_collections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            catalog_id UUID REFERENCES stac_catalogs(id) ON DELETE SET NULL,
            stac_collection TEXT NOT NULL,
            bbox FLOAT8[4],
            date_start DATE,
            date_end DATE,
            query_params JSONB DEFAULT '{}'::jsonb,
            scene_count INT DEFAULT 0,
            index_path TEXT,
            status TEXT NOT NULL DEFAULT 'indexing',
            error TEXT,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_stac_collections_status ON stac_collections (status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_stac_collections_created_by ON stac_collections (created_by)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS stac_scenes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            collection_id UUID NOT NULL REFERENCES stac_collections(id) ON DELETE CASCADE,
            stac_item_id TEXT NOT NULL,
            datetime TIMESTAMPTZ,
            cloud_cover FLOAT,
            bbox FLOAT8[4],
            bands JSONB DEFAULT '{}'::jsonb,
            properties JSONB DEFAULT '{}'::jsonb,
            thumbnail_url TEXT,
            dggs_coverage TEXT[] DEFAULT '{}',
            ingested BOOLEAN NOT NULL DEFAULT FALSE,
            dataset_id UUID REFERENCES datasets(id) ON DELETE SET NULL,
            UNIQUE(collection_id, stac_item_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_stac_scenes_collection ON stac_scenes (collection_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_stac_scenes_datetime ON stac_scenes (datetime)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_stac_scenes_ingested ON stac_scenes (ingested)")

    op.execute(
        """
        INSERT INTO stac_catalogs (name, api_url, catalog_type, auth_type, collections) VALUES
            ('earth-search-v1', 'https://earth-search.aws.element84.com/v1', 'api', NULL,
             '["sentinel-2-l2a", "landsat-c2-l2", "cop-dem-glo-30", "cop-dem-glo-90", "sentinel-1-grd"]'::jsonb),
            ('planetary-computer', 'https://planetarycomputer.microsoft.com/api/stac/v1', 'api', 'planetary_computer',
             '["sentinel-2-l2a", "landsat-c2-l2", "naip", "alos-dem", "esa-worldcover"]'::jsonb),
            ('usgs-landsat', 'https://landsatlook.usgs.gov/stac-server', 'api', NULL,
             '["landsat-c2l2-sr", "landsat-c2l2-st"]'::jsonb)
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade():
    """No-op downgrade.

    This revision repairs schema drift and may move live data between tables.
    Reversing it safely is not supported.
    """
    pass
