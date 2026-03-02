CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS parcels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  edge_parcel_id TEXT UNIQUE NOT NULL,
  qdrant_point_id TEXT NOT NULL,
  image_object_key TEXT NOT NULL,
  camera_id TEXT NOT NULL,
  fingerprint_dim INT NOT NULL,
  metadata_enc BYTEA NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS parcel_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  edge_parcel_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sync_outbox (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  destination TEXT NOT NULL,
  payload JSONB NOT NULL,
  status TEXT NOT NULL,
  retries INT NOT NULL DEFAULT 0,
  next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS routing_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_name TEXT NOT NULL,
  rule_expression JSONB NOT NULL,
  destination TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS camera_status (
  camera_id TEXT PRIMARY KEY,
  last_seen TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL
);
