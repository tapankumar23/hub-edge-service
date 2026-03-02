# Prompt Context (For LLMs)

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Purpose:** Condensed system context for AI-assisted development. Keep this file current.

---

## System Summary

Edge Hub is a production-grade, Kafka-first edge pipeline that ingests camera images, detects parcels using YOLO ONNX, embeds them into 768-dim vectors, resolves identity via Qdrant cosine nearest-neighbor, persists state in Postgres, syncs to cloud via outbox pattern, and returns routing decisions. All services run in Docker Compose on an edge host.

---

## Key Entities

| Entity | Schema |
|--------|--------|
| `FrameEvent` | `{ schema_version: 1, camera_id, timestamp_ms, image_base64 }` |
| `InferenceResult` | `{ schema_version: 1, camera_id, timestamp, detections[], fingerprint[768], image_object_key }` |
| `Detection` | `{ x1, y1, x2, y2, score, label }` |
| `Parcel` (Postgres) | `{ edge_parcel_id (UUID PK), qdrant_point_id, image_object_key, camera_id, fingerprint_dim, metadata_enc, enc_key_version }` |
| `ParcelEvent` (Postgres) | `{ id, edge_parcel_id (FK), event_type, payload (JSONB), created_at }` |
| `SyncOutbox` (Postgres) | `{ id, destination, payload (JSONB), status (pending/sent/failed), retry_count }` |
| `RoutingRule` (Postgres) | `{ rule_name (edge_parcel_id), destination, enabled }` |

---

## Services & Ports

| Service | Port | Key APIs |
|---------|------|---------|
| camera-ingestion | 8081 | `POST /ingest { camera_id?, image_base64 }` → 202 |
| edge-services (inference) | 8082 | `POST /infer { image_base64?, object_key?, camera_id? }` → InferenceResult |
| edge-services (identity) | 8083 | `POST /identify { inference, metadata? }` → `{ edge_parcel_id, match_score, qdrant_point_id, is_new }` |
| edge-services (sync) | 8084 | `GET /sync/status` → `{ pending, sent_last_hour }` |
| edge-services (routing) | 8085 | `POST /route { edge_parcel_id, metadata? }` → `{ destination, source }` / `POST /route/rules` |
| edge-services (monitoring) | 8086 | `GET /metrics` (Prometheus) |
| ui-dashboard | 3000 | Operator UI (Next.js) |
| Redpanda | 9092 | Kafka broker |
| Postgres | 5432 | Relational DB |
| MinIO API | 9000 | S3-compatible object storage |
| Qdrant | 6334→6333 | Vector database |
| Prometheus | 9090 | Metrics |
| Grafana | 3001 | Dashboards |

---

## Data Flows

```
POST /ingest → frames topic → inference (ONNX+embed) → MinIO + inference_results topic
  → identity (Qdrant search + Postgres write + sync_outbox)
    → sync service (poll → CLOUD_SYNC_URL)
    → routing service (/route → local rule | cloud API | LOCAL_DEFAULT)
```

---

## Stores

| Store | Purpose | Key Config |
|-------|---------|-----------|
| Kafka (Redpanda) | `frames` (1h retention, 4 partitions), `inference_results` (24h, 4 partitions) | Consumer groups: `edge-inference-consumer`, `edge-identity-consumer` |
| MinIO | bucket `parcels`; keys `capture/{edge_parcel_id}.jpg` | S3-compatible; TLS in prod |
| Qdrant | collection `parcel_fingerprints`; size=768; Cosine | point payload: `{ edge_parcel_id, camera_id, model_version }` |
| Postgres 15 | tables: `parcels`, `parcel_events`, `routing_rules`, `sync_outbox` | Migrations via Flyway; indexes on FK columns + status fields |

---

## Key Configuration

| Env Var | Service | Default | Notes |
|---------|---------|---------|-------|
| `ENCRYPTION_KEY` | identity | REQUIRED | AES-256-GCM; 32 bytes hex |
| `FINGERPRINT_MATCH_THRESHOLD` | identity | 0.85 | Cosine similarity threshold |
| `LOCAL_DEFAULT` | routing | REQUIRED | Fallback destination |
| `CLOUD_SYNC_URL` | sync | (none) | Optional; items marked sent locally if absent |
| `ROUTING_API_URL` | routing | (none) | Optional cloud routing override |
| `ROLE` | edge-services | REQUIRED | inference / identity / sync / routing / monitoring |
| `LOG_LEVEL` | all | INFO | |

---

## Invariants (Do Not Violate)

- Kafka topic names `frames` and `inference_results` are stable.
- Consumer group names `edge-inference-consumer` and `edge-identity-consumer` are stable.
- `fingerprint` dimension is always 768.
- Qdrant collection `parcel_fingerprints` uses Cosine distance; changing this invalidates all vectors.
- MinIO bucket name `parcels` is stable.
- `edge_parcel_id` is UUIDv4 and immutable.
- `POST /route` MUST always return HTTP 200 with a `destination` (never 503).
- `metadata_enc` raw value MUST never appear in logs.
- All schema changes to Kafka messages must be backward-compatible (add optional fields only) or include a `schema_version` bump.
- edge-services roles are mutually exclusive per instance.

---

## Error Behaviors (Summarized)

| Failure | Behavior |
|---------|---------|
| Postgres down | `/health` stays 200; writes skipped; routing uses cloud/default |
| Qdrant down | Identity treats all as new_identity; circuit breaker opens after 3 failures |
| MinIO down | Inference skips upload; `image_object_key = ""`; pipeline continues |
| Kafka down | Consumers halt + reconnect with backoff; producers retry 5× |
| Cloud sync 5xx | Outbox row stays `pending`; retry next poll cycle |
| Cloud sync 4xx | Outbox row marked `failed`; no retry |
| Cloud routing timeout (2s) | Returns `LOCAL_DEFAULT` with `source: "local-default"` |
| Empty `image_base64` | HTTP 400 |
| No YOLO detections | Zero vector; `new_identity` likely; pipeline continues |

---

## Testing

| Test | Command | What It Validates |
|------|---------|------------------|
| Health checks | `./scripts/health_check.sh` | All services 2xx on `/health` |
| P0 E2E | `./scripts/e2e.sh` | Full ingest → inference → identity → sync → routing |
| Integration | `pytest tests/integration/` | Per-service-boundary with live stack |
| Performance baseline | `k6 run --vus 1 --iterations 50 scripts/perf/k6_baseline.js` | Latency SLOs on dev hardware |

---

## Documentation Map

| Need | Document |
|------|---------|
| Why this exists | 01_product_vision.md |
| What must be built | 02_business_requirements.md |
| Who needs what | 03_user_stories.md |
| How each service works | 02_functional_spec.md |
| API schemas | 07_api_contracts.yaml (OpenAPI 3.0) |
| DB / Kafka schemas | 06_data_model_spec.md |
| Kafka topics / DLQ | 05_eventing_and_async_flows.md |
| Component topology | 01_system_architecture.md |
| SLOs and NFRs | 01_non_functional_requirements.md |
| Run P0 test | 02_acceptance_test_spec.md |
| Integration tests | 03_integration_test_spec.md |
| Performance tests | 04_performance_test_spec.md |
| Failure modes | 05_failure_modes_and_edge_cases.md |
| Req ↔ test coverage | 06_traceability_matrix.md |
| Metrics / alerts / logs | 01_observability_spec.md |
| Version pinning / invariants | 03_constraints_and_invariants.md |
| Deployment runbooks | 02_deployment_and_operations.md |
