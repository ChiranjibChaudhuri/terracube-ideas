"""Initial schema migration

This migration creates the initial database schema for TerraCube IDEAS,
including the new RBAC fields added in session 1.

Revision ID: 001
Revises:
Create Date: 2026-02-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create initial tables."""
    # Users table with RBAC fields
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('name', sa.String()),
        sa.Column('role', sa.String(), nullable=False, server_default='viewer'),  # RBAC
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),  # RBAC
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Datasets table with visibility fields
    op.create_table(
        'datasets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String()),
        sa.Column('dggs_name', sa.String(), server_default='IVEA3H'),
        sa.Column('level', sa.Integer()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), ondelete='SET NULL'),
        sa.Column('status', sa.String(), server_default='active'),
        sa.Column('metadata', postgresql.JSON(), server_default='{}'),
        sa.Column('visibility', sa.String(), nullable=False, server_default='private'),  # RBAC
        sa.Column('shared_with', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default=[]),  # RBAC
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Attributes registry
    op.create_table(
        'attributes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('key', sa.String(), unique=True, nullable=False),
        sa.Column('description', sa.String()),
        sa.Column('unit', sa.String()),
        sa.Column('data_type', sa.String()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Uploads table
    op.create_table(
        'uploads',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('datasets.id'), ondelete='SET NULL'),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('mime_type', sa.String()),
        sa.Column('size_bytes', sa.BigInteger()),
        sa.Column('storage_key', sa.String(), nullable=False),
        sa.Column('status', sa.String(), server_default='staged'),
        sa.Column('error', sa.String()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # DGGS Topology table
    op.create_table(
        'dgg_topology',
        sa.Column('dggid', sa.String(), nullable=False),
        sa.Column('neighbor_dggid', sa.String(), nullable=False),
        sa.Column('parent_dggid', sa.String()),
        sa.Column('level', sa.Integer()),
        sa.PrimaryKey('dggid', 'neighbor_dggid'),
    )
    op.create_index('idx_dgg_topology_dggid', 'dgg_topology', ['dggid'])
    op.create_index('idx_dgg_topology_parent', 'dgg_topology', ['parent_dggid'])

    # Cell objects partitioned table
    # Note: This is the default partition template
    # Actual partitions will be created as cell_objects_{dataset_id}
    op.create_table(
        'cell_objects_default',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('dggid', sa.String(), nullable=False),
        sa.Column('tid', sa.Integer(), nullable=False),
        sa.Column('attr_key', sa.String(), nullable=False),
        sa.Column('value_text', sa.String()),
        sa.Column('value_num', sa.Float(precision=53)),
        sa.Column('value_json', postgresql.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKey('id', 'dataset_id'),
        sa.UniqueConstraint('dataset_cell_unique', 'dataset_id', 'dggid', 'tid', 'attr_key'),
    )
    op.create_index('idx_cell_objects_default_dataset_id', 'cell_objects_default', ['dataset_id'])
    op.create_index('idx_cell_objects_default_dggid', 'cell_objects_default', ['dggid'])
    op.create_index('idx_cell_objects_default_attr_key', 'cell_objects_default', ['attr_key'])
    op.create_index('idx_cell_objects_default_tid', 'cell_objects_default', ['tid'])

    # Annotations tables (from models_annotations.py)
    op.create_table(
        'annotations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('dggid', sa.String(), nullable=False),
        sa.Column('tid', sa.Integer()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), ondelete='SET NULL'),
        sa.Column('visibility', sa.String(), nullable=False, server_default='private'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'cell_annotations',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('annotation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('annotations.id'), primary_key=True),
        sa.Column('dggid', sa.String(), nullable=False),
        sa.Column('tid', sa.Integer()),
        sa.PrimaryKey('id', 'annotation_id', 'dggid', 'tid'),
    )

    op.create_index('idx_cell_annotations_annotation_id', 'cell_annotations', ['annotation_id'])
    op.create_index('idx_cell_annotations_dggid', 'cell_annotations', ['dggid'])

    op.create_table(
        'annotation_shares',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('annotation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('annotations.id'), primary_key=True),
        sa.Column('shared_with', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.PrimaryKey('id', 'annotation_id', 'shared_with'),
    )


def downgrade():
    """Drop all tables."""
    # Drop in reverse order of dependencies
    op.drop_table('annotation_shares')
    op.drop_table('cell_annotations')
    op.drop_table('annotations')
    op.drop_table('cell_objects_default')
    op.drop_index('idx_dgg_topology_dggid', 'dgg_topology')
    op.drop_index('idx_dgg_topology_parent', 'dgg_topology')
    op.drop_table('dgg_topology')
    op.drop_table('uploads')
    op.drop_table('attributes')
    op.drop_table('datasets')
    op.drop_table('users')
