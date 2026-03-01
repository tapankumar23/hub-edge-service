# Constraints & Invariants

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** Edge Platform Architecture | **Review Cadence:** Quarterly

---

## Technology Version Pinning

All production containers must use pinned image tags. No `latest` tags in production.

| Component | Pinned Version | Notes |
|-----------|---------------|-------|
| Python | 3.11.x | Base image: `python:3.11-slim` |
| Go | 1.22.x | Base image: `golang:1.22-alpine` |
| Node.js | 20.x LTS | Base image: `node:20-alpine` |
| Postgres | 15.x | `postgres:15` |
| Redpanda | 23.x | `redpandadata/redpanda:v23.x.y` |
| MinIO | RELEASE.2024-xx | Pinned monthly release |
| Qdrant | 1.7.x | `qdrant/qdrant:v1.7.x` |
| Redis | 7.x | `redis:7-alpine` |
| Prometheus | 2.48.x | `prom/prometheus:v2.48.x` |
| Grafana | 10.x | `grafana/grafana:10.x.x` |
| ONNX Runtime | 1.17.x | Pinned in `requirements.txt` |
| aiokafka | 0.10.x | Pinned in `requirements.txt` |
| boto3 | 1.34.x | Pinned in `requirements.txt` |

**Version update policy:**
- Patch updates: apply within 30 days of release.
- Minor updates: review compatibility; apply within 60 days.
- Major updates: Architecture Review Board sign-off required; plan migration.

---

## Protocol & Topic Invariants

### Kafka Topics (Names Are Stable)

Renaming a Kafka topic is a breaking change requiring full consumer migration.

| Topic | Name | Invariant |
|-------|------|----------|
| Image frames | `frames` | MUST NOT be renamed |
| Inference results | `inference_results` | MUST NOT be renamed |
| Frame DLQ | `frames.DLQ` | MUST NOT be renamed |
| Inference DLQ | `inference_results.DLQ` | MUST NOT be renamed |

### Consumer Groups (Names Are Stable)

| Consumer Group | Topic | Service |
|---------------|-------|---------|
| `edge-inference-consumer` | `frames` | edge-inference |
| `edge-identity-consumer` | `inference_results` | edge-identity |

---

## Message Schema Invariants

Schemas are backward-compatible by default. See [05_eventing_and_async_flows.md](05_eventing_and_async_flows.md) for versioning rules.

| Schema | Invariant |
|--------|----------|
| `FrameEvent.camera_id` | MUST remain string; MUST NOT be renamed |
| `FrameEvent.timestamp_ms` | MUST remain integer Unix milliseconds |
| `FrameEvent.image_base64` | MUST remain base64 string; MUST NOT be removed |
| `InferenceResult.fingerprint` | MUST remain float array of length 768 |
| `InferenceResult.detections` | MUST remain array; items MUST contain x1, y1, x2, y2, score, label |
| `schema_version` | MUST increment for any breaking schema change |

---

## Storage Invariants

### MinIO

| Property | Invariant |
|----------|----------|
| Bucket name | `parcels` — MUST NOT be changed without migration plan |
| Default key pattern | `capture/{uuid}.jpg` — MUST NOT change format |
| Bucket versioning | Disabled; keys are unique per edge_parcel_id |

### Qdrant

| Property | Invariant |
|----------|----------|
| Collection name | `parcel_fingerprints` — MUST NOT be renamed |
| Vector size | 768 — MUST match embedding model output dimension |
| Distance metric | `Cosine` — MUST NOT change (changes invalidate all existing comparisons) |
| Payload field | `edge_parcel_id` — MUST be present in every point |

### Postgres

| Property | Invariant |
|----------|----------|
| `edge_parcel_id` | UUIDv4; immutable after creation; MUST NOT be changed |
| `event_type` valid values | Set of values defined in Data Model Spec (doc 06); additions allowed; removals require migration |
| `sync_outbox.status` | Only `pending`, `sent`, `failed`; MUST NOT add values without schema migration |
| FK cascade on `parcels` delete | `parcel_events` cascades; intended for GDPR deletion only |

---

## Threshold Invariants

| Threshold | Config | Invariant |
|-----------|--------|----------|
| Fingerprint match | `FINGERPRINT_MATCH_THRESHOLD` (float 0–1) | Must be configurable via env; default 0.85; MUST NOT be hardcoded |
| Sync poll interval | `SYNC_POLL_INTERVAL_SECONDS` | Default 10 s; configurable |
| Sync batch size | `SYNC_BATCH_SIZE` | Default 10; configurable |
| Routing cloud timeout | 2 s | Hardcoded; change requires code release |
| Max payload size | 10 MB | Hardcoded at ingestion; change requires code release |

---

## Service Role Invariants

- `edge-services` `ROLE` env determines which background consumers/producers run.
- Roles are **mutually exclusive per instance**: one instance = one role.
- Valid roles: `inference`, `identity`, `sync`, `routing`, `monitoring`.
- An instance with an invalid role MUST log CRITICAL and exit.

---

## API Contract Invariants

- API paths MUST NOT be changed without versioning (`/v2/...`).
- HTTP method for existing endpoints MUST NOT change.
- Required request fields MUST NOT be removed.
- Response field names MUST NOT be changed (backward-compat add-only).

---

## Breaking Change Policy

A breaking change is defined as:
- Renaming or removing a Kafka topic or consumer group.
- Changing a Kafka message schema field name, type, or removing a required field.
- Renaming or removing an API endpoint path or method.
- Changing the vector dimension or distance metric in Qdrant.
- Removing or renaming a Postgres column used by any service.

**Breaking change process:**
1. Open a design RFC document and assign to Architecture Review Board.
2. ARB sign-off required before implementation begins.
3. Plan a migration window with dual-read/dual-write where applicable.
4. Update Traceability Matrix and all affected specs.
5. Document rollback plan before deploying.

---

## Backward Compatibility Guarantees

For minor releases (patch and minor version bumps):
- All API responses remain parseable by clients built against the previous minor version.
- All Kafka messages remain parseable by consumers built against the previous minor version.
- Schema additions (new optional fields) are the only permitted change.
- Database migrations are additive only (new columns with defaults; new tables; new indexes).

Major version bumps remove backward compatibility guarantees and require migration documentation.
