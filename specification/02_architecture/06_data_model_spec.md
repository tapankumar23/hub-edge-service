# Data Model Specification

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** Edge Platform Engineering | **Review Cadence:** Per Release

---

## Relational Database — Postgres 15+

### Migration Strategy
- Migrations managed via Flyway (or Alembic for Python services).
- Migration files in `db/migrations/`, numbered sequentially: `V001__initial_schema.sql`, `V002__add_index.sql`.
- Migrations run automatically in Docker Compose via `db-migrate` init container before services start.
- Breaking schema changes (column removal, type changes) require a multi-step migration with backward-compatible intermediate state.
- Rollback scripts required for all changes beyond `V001`.

### Data Retention Policy

| Table | Active Retention | Archival Strategy |
|-------|-----------------|-------------------|
| `parcels` | Indefinite (immutable identity) | Cold storage after 2 years |
| `parcel_events` | 90 days | Compressed Parquet in MinIO `archive` bucket after 90 days |
| `routing_rules` | Indefinite (operational config) | None |
| `sync_outbox` | 30 days post-`sent` | Nightly cleanup job deletes sent rows > 30 days; failed rows > 7 days |

---

### Table: `parcels`

```sql
CREATE TABLE parcels (
    edge_parcel_id         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    qdrant_point_id        UUID         NOT NULL,
    image_object_key       TEXT         NOT NULL DEFAULT '',
    camera_id              VARCHAR(128) NOT NULL DEFAULT 'unknown',
    fingerprint_dim        SMALLINT     NOT NULL DEFAULT 768,
    damage_classification  JSONB,                    -- { "type": "none"|"minor"|"major", "confidence": float }; NULL if not detected
    metadata_enc           BYTEA,                    -- AES-256-GCM ciphertext; nonce prepended; NULL if no metadata
    enc_key_version        SMALLINT     NOT NULL DEFAULT 1,
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_parcels_qdrant_point_id ON parcels(qdrant_point_id);
CREATE INDEX idx_parcels_camera_id              ON parcels(camera_id);
CREATE INDEX idx_parcels_created_at             ON parcels(created_at DESC);

CREATE TRIGGER trg_parcels_updated_at
    BEFORE UPDATE ON parcels
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

| Column | Type | Constraints | Notes |
|--------|------|------------|-------|
| `edge_parcel_id` | UUID | PK | UUIDv4; generated at identity resolution; stable across all systems |
| `qdrant_point_id` | UUID | NOT NULL, UNIQUE | Must match Qdrant collection point ID |
| `image_object_key` | TEXT | NOT NULL | MinIO key; `''` when MinIO unavailable |
| `camera_id` | VARCHAR(128) | NOT NULL | Source camera; `'unknown'` as fallback |
| `fingerprint_dim` | SMALLINT | NOT NULL | Vector dimensionality; always 768 |
| `damage_classification` | JSONB | NULL allowed | Shape: `{ "type": "none"\|"minor"\|"major", "confidence": 0.0–1.0 }`; NULL when no confidence ≥ threshold |
| `metadata_enc` | BYTEA | NULL allowed | AES-256-GCM; NULL when no metadata |
| `enc_key_version` | SMALLINT | NOT NULL | Tracks key version for rotation |

---

### Table: `parcel_events`

```sql
CREATE TABLE parcel_events (
    id             BIGSERIAL    PRIMARY KEY,
    edge_parcel_id UUID         NOT NULL REFERENCES parcels(edge_parcel_id) ON DELETE CASCADE,
    event_type     VARCHAR(64)  NOT NULL,
    payload        JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_parcel_events_parcel_id   ON parcel_events(edge_parcel_id);
CREATE INDEX idx_parcel_events_event_type  ON parcel_events(event_type);
CREATE INDEX idx_parcel_events_created_at  ON parcel_events(created_at DESC);
CREATE INDEX idx_parcel_events_parcel_type ON parcel_events(edge_parcel_id, event_type);
```

**`event_type` Enum Values:**

| Value | Trigger |
|-------|---------|
| `identified` | Existing parcel matched via vector search |
| `new_identity` | New parcel created; first-time observation |
| `sync_enqueued` | Parcel queued in sync_outbox |
| `sync_sent` | sync_outbox item delivered to cloud |
| `routed` | Routing decision made |

**FK Cascade:** `ON DELETE CASCADE` — removing a parcel removes all events (correction/GDPR deletion only).

---

### Table: `routing_rules`

```sql
CREATE TABLE routing_rules (
    rule_name    VARCHAR(255) PRIMARY KEY,   -- edge_parcel_id or named pattern
    destination  VARCHAR(255) NOT NULL,
    enabled      BOOLEAN      NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_routing_rules_enabled ON routing_rules(enabled) WHERE enabled = true;

CREATE TRIGGER trg_routing_rules_updated_at
    BEFORE UPDATE ON routing_rules
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

**Notes:** Partial index on `enabled = true` optimizes the hot read path. `rule_name` is typically an `edge_parcel_id` string but supports named patterns for future wildcard matching.

---

### Table: `sync_outbox`

```sql
CREATE TABLE sync_outbox (
    id          BIGSERIAL    PRIMARY KEY,
    destination VARCHAR(128) NOT NULL DEFAULT 'cloud_registry',
    payload     JSONB        NOT NULL,
    status      VARCHAR(16)  NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'sent', 'failed')),
    retry_count SMALLINT     NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    sent_at     TIMESTAMPTZ
);

CREATE INDEX idx_sync_outbox_pending    ON sync_outbox(status) WHERE status = 'pending';
CREATE INDEX idx_sync_outbox_created_at ON sync_outbox(created_at DESC);
```

**Status Transitions:**
```
pending → sent    (cloud returns 200)
pending → failed  (cloud returns 4xx — permanent; do not retry)
pending → pending (cloud returns 5xx or timeout — retry next poll cycle)
```

---

### Shared Utility

```sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

## Vector Store — Qdrant

### Collection: `parcel_fingerprints`

```json
{
  "collection_name": "parcel_fingerprints",
  "vectors": { "size": 768, "distance": "Cosine" },
  "optimizers_config": { "default_segment_number": 2 },
  "replication_factor": 1
}
```

**Point Payload Schema:**
```json
{
  "edge_parcel_id": "<uuid>",
  "camera_id":      "<string>",
  "created_at":     "<ISO 8601>",
  "model_version":  "<string>"
}
```

- `model_version` enables filtering during re-embedding migrations.
- Collection created automatically by identity service on startup if absent.
- Replication factor 1 for single-node edge; increase for HA Qdrant cluster in production.

---

## Object Storage — MinIO

| Property | Value |
|----------|-------|
| Bucket | `parcels` |
| Versioning | Disabled (immutable keys per UUID) |
| Lifecycle | Objects > 365 days moved to `parcels-archive` |

**Key Conventions:**

| Pattern | Usage |
|---------|-------|
| `capture/{edge_parcel_id}.jpg` | Default; stored by inference service |
| `<caller-provided object_key>` | When `/infer` request includes `object_key` |

---

## Message Schemas (Kafka)

See [05_eventing_and_async_flows.md](05_eventing_and_async_flows.md) for topic configuration.

### `FrameEvent`
```json
{
  "schema_version": 1,
  "camera_id":    "cam-01",
  "timestamp_ms": 1740873600000,
  "image_base64": "<base64 string>"
}
```

### `InferenceResult`
```json
{
  "schema_version":    1,
  "camera_id":         "cam-01",
  "timestamp":         1740873600000,
  "detections": [
    { "x1": 10.0, "y1": 20.0, "x2": 100.0, "y2": 200.0, "score": 0.95, "label": "parcel" }
  ],
  "fingerprint":       [0.01, -0.23, ...],
  "image_object_key":  "capture/550e8400-e29b-41d4-a716-446655440000.jpg"
}
```
