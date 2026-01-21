CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text UNIQUE NOT NULL,
  password_hash text NOT NULL,
  name text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS datasets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  description text,
  dggs_name text NOT NULL DEFAULT 'IVEA3H',
  level integer,
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  status text NOT NULL DEFAULT 'active',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS attributes (
  id bigserial PRIMARY KEY,
  key text UNIQUE NOT NULL,
  description text,
  unit text,
  data_type text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cell_objects (
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
) PARTITION BY LIST (dataset_id);

-- Default partition for datasets without explicit partition (required for inserts to work)
CREATE TABLE IF NOT EXISTS cell_objects_default PARTITION OF cell_objects DEFAULT;

CREATE INDEX IF NOT EXISTS idx_cell_objects_dataset_id ON cell_objects (dataset_id);
CREATE INDEX IF NOT EXISTS idx_cell_objects_dataset_dggid ON cell_objects (dataset_id, dggid);
CREATE INDEX IF NOT EXISTS idx_cell_objects_dggid ON cell_objects (dggid);
CREATE INDEX IF NOT EXISTS idx_cell_objects_attr_key ON cell_objects (attr_key);
CREATE INDEX IF NOT EXISTS idx_cell_objects_tid ON cell_objects (tid);

CREATE TABLE IF NOT EXISTS uploads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id uuid REFERENCES datasets(id) ON DELETE SET NULL,
  filename text NOT NULL,
  mime_type text,
  size_bytes bigint,
  storage_key text NOT NULL,
  status text NOT NULL DEFAULT 'staged',
  error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads (status);
