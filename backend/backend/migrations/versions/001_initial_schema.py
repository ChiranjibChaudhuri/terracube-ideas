"""Initial schema migration.

Revision ID: 001
Revises:
Create Date: 2026-02-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create the canonical initial schema for fresh Alembic installs."""
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("name", sa.String()),
        sa.Column("role", sa.String(), nullable=False, server_default=sa.text("'viewer'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String()),
        sa.Column("dggs_name", sa.String(), nullable=False, server_default=sa.text("'IVEA3H'")),
        sa.Column("level", sa.Integer()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("visibility", sa.String(), nullable=False, server_default=sa.text("'private'")),
        sa.Column(
            "shared_with",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "attributes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(), unique=True, nullable=False),
        sa.Column("description", sa.String()),
        sa.Column("unit", sa.String()),
        sa.Column("data_type", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.execute(
        """
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
        """
    )
    op.execute("CREATE TABLE cell_objects_default PARTITION OF cell_objects DEFAULT")
    op.create_index("idx_cell_objects_dataset_id", "cell_objects", ["dataset_id"])
    op.create_index("idx_cell_objects_dataset_dggid", "cell_objects", ["dataset_id", "dggid"])
    op.create_index("idx_cell_objects_dggid", "cell_objects", ["dggid"])
    op.create_index("idx_cell_objects_attr_key", "cell_objects", ["attr_key"])
    op.create_index("idx_cell_objects_tid", "cell_objects", ["tid"])

    op.create_table(
        "uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("datasets.id", ondelete="SET NULL")),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String()),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'staged'")),
        sa.Column("error", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_uploads_status", "uploads", ["status"])

    op.create_table(
        "dgg_topology",
        sa.Column("dggid", sa.String(), nullable=False),
        sa.Column("neighbor_dggid", sa.String(), nullable=False),
        sa.Column("parent_dggid", sa.String()),
        sa.Column("level", sa.Integer()),
        sa.PrimaryKeyConstraint("dggid", "neighbor_dggid"),
    )
    op.create_index("idx_dgg_topology_dggid", "dgg_topology", ["dggid"])
    op.create_index("idx_dgg_topology_parent", "dgg_topology", ["parent_dggid"])

    op.create_table(
        "annotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cell_dggid", sa.String(length=50), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("annotation_type", sa.String(length=50), nullable=False, server_default=sa.text("'note'")),
        sa.Column("visibility", sa.String(length=20), nullable=False, server_default=sa.text("'private'")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_annotations_cell", "annotations", ["cell_dggid"])
    op.create_index("idx_annotations_dataset", "annotations", ["dataset_id"])
    op.create_index("idx_annotations_type", "annotations", ["annotation_type"])
    op.create_index("idx_annotations_visibility", "annotations", ["visibility"])
    op.create_index("idx_annotations_created_by", "annotations", ["created_by"])

    op.create_table(
        "cell_annotations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("annotation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("annotations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cell_dggid", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("annotation_id", "cell_dggid", name="uq_cell_annotations"),
    )
    op.create_index("idx_cell_annotations_annotation", "cell_annotations", ["annotation_id"])
    op.create_index("idx_cell_annotations_cell", "cell_annotations", ["cell_dggid"])

    op.create_table(
        "annotation_shares",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("annotation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("annotations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shared_with", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("annotation_id", "shared_with", name="uq_annotation_shares"),
    )
    op.create_index("idx_annotation_shares_annotation", "annotation_shares", ["annotation_id"])
    op.create_index("idx_annotation_shares_user", "annotation_shares", ["shared_with"])

    op.create_table(
        "stac_catalogs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("api_url", sa.Text(), nullable=False),
        sa.Column("catalog_type", sa.Text(), nullable=False, server_default=sa.text("'api'")),
        sa.Column("auth_type", sa.Text()),
        sa.Column("collections", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "stac_collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("catalog_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stac_catalogs.id", ondelete="SET NULL")),
        sa.Column("stac_collection", sa.Text(), nullable=False),
        sa.Column("bbox", postgresql.ARRAY(sa.Float(precision=53))),
        sa.Column("date_start", sa.Date()),
        sa.Column("date_end", sa.Date()),
        sa.Column("query_params", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb")),
        sa.Column("scene_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("index_path", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'indexing'")),
        sa.Column("error", sa.Text()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_stac_collections_status", "stac_collections", ["status"])
    op.create_index("idx_stac_collections_created_by", "stac_collections", ["created_by"])

    op.create_table(
        "stac_scenes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stac_collections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stac_item_id", sa.Text(), nullable=False),
        sa.Column("datetime", sa.DateTime(timezone=True)),
        sa.Column("cloud_cover", sa.Float(precision=53)),
        sa.Column("bbox", postgresql.ARRAY(sa.Float(precision=53))),
        sa.Column("bands", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb")),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb")),
        sa.Column("thumbnail_url", sa.Text()),
        sa.Column("dggs_coverage", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'")),
        sa.Column("ingested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("datasets.id", ondelete="SET NULL")),
        sa.UniqueConstraint("collection_id", "stac_item_id"),
    )
    op.create_index("idx_stac_scenes_collection", "stac_scenes", ["collection_id"])
    op.create_index("idx_stac_scenes_datetime", "stac_scenes", ["datetime"])
    op.create_index("idx_stac_scenes_ingested", "stac_scenes", ["ingested"])

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
    """Drop all schema objects created by the initial migration."""
    op.drop_index("idx_stac_scenes_ingested", table_name="stac_scenes")
    op.drop_index("idx_stac_scenes_datetime", table_name="stac_scenes")
    op.drop_index("idx_stac_scenes_collection", table_name="stac_scenes")
    op.drop_table("stac_scenes")

    op.drop_index("idx_stac_collections_created_by", table_name="stac_collections")
    op.drop_index("idx_stac_collections_status", table_name="stac_collections")
    op.drop_table("stac_collections")

    op.drop_table("stac_catalogs")

    op.drop_index("idx_annotation_shares_user", table_name="annotation_shares")
    op.drop_index("idx_annotation_shares_annotation", table_name="annotation_shares")
    op.drop_table("annotation_shares")

    op.drop_index("idx_cell_annotations_cell", table_name="cell_annotations")
    op.drop_index("idx_cell_annotations_annotation", table_name="cell_annotations")
    op.drop_table("cell_annotations")

    op.drop_index("idx_annotations_created_by", table_name="annotations")
    op.drop_index("idx_annotations_visibility", table_name="annotations")
    op.drop_index("idx_annotations_type", table_name="annotations")
    op.drop_index("idx_annotations_dataset", table_name="annotations")
    op.drop_index("idx_annotations_cell", table_name="annotations")
    op.drop_table("annotations")

    op.drop_index("idx_dgg_topology_parent", table_name="dgg_topology")
    op.drop_index("idx_dgg_topology_dggid", table_name="dgg_topology")
    op.drop_table("dgg_topology")

    op.drop_index("idx_uploads_status", table_name="uploads")
    op.drop_table("uploads")

    op.drop_index("idx_cell_objects_tid", table_name="cell_objects")
    op.drop_index("idx_cell_objects_attr_key", table_name="cell_objects")
    op.drop_index("idx_cell_objects_dggid", table_name="cell_objects")
    op.drop_index("idx_cell_objects_dataset_dggid", table_name="cell_objects")
    op.drop_index("idx_cell_objects_dataset_id", table_name="cell_objects")
    op.execute("DROP TABLE cell_objects_default")
    op.execute("DROP TABLE cell_objects")

    op.drop_table("attributes")
    op.drop_table("datasets")
    op.drop_table("users")
