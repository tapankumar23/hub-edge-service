# Non-Functional Requirements

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** Edge Platform Engineering + SRE | **Review Cadence:** Quarterly

---

## Availability

| Service / Component | Availability Target | Measurement Window | Notes |
|--------------------|--------------------|-------------------|-------|
| camera-ingestion | 99.9% | 30-day rolling | Stateless; 2 replicas in prod |
| edge-services (inference) | 99.5% | 30-day rolling | GPU unavailability tolerated; CPU fallback |
| edge-services (identity) | 99.9% | 30-day rolling | Kafka at-least-once; missing writes retried |
| edge-services (sync) | 99.0% | 30-day rolling | Sync lag tolerated; outbox persists state |
| edge-services (routing) | 99.9% | 30-day rolling | Must always return a destination |
| Postgres | 99.9% | 30-day rolling | Primary + replica; auto-failover < 60 s |
| Redpanda | 99.5% | 30-day rolling | 3-node cluster; leader election < 30 s |
| MinIO | 99.0% | 30-day rolling | Image storage; degraded mode acceptable |
| Qdrant | 99.5% | 30-day rolling | Identity degrades to new-parcel on unavailability |
| System-wide (full pipeline) | 99.0% | 30-day rolling | Composite of all critical path services |

**Downtime budget (99.9%):** 43.8 minutes/month.

---

## Latency SLOs

| Operation | p50 | p95 | p99 | Measured At |
|-----------|-----|-----|-----|-------------|
| `POST /ingest` response | < 100 ms | < 250 ms | < 500 ms | camera-ingestion |
| E2E: ingest → inference_results | < 500 ms | < 1.5 s | < 3 s | Prometheus histogram |
| ONNX inference (CPU) | < 400 ms | < 1 s | < 2 s | edge-inference |
| ONNX inference (GPU) | < 100 ms | < 200 ms | < 400 ms | edge-inference |
| MinIO `put_object` | < 200 ms | < 500 ms | < 1 s | edge-inference |
| Qdrant vector search | < 50 ms | < 150 ms | < 300 ms | edge-identity |
| `POST /route` response | < 50 ms | < 200 ms | < 500 ms | edge-routing |
| Cloud routing API (timeout) | 2 s hard timeout | — | — | edge-routing |
| Postgres query (read) | < 10 ms | < 50 ms | < 100 ms | all services |

---

## Throughput

| Metric | Dev Target | Production Target |
|--------|-----------|-----------------|
| Frames ingested per minute | 10 | 300 (100 parcels/hour × 3 cameras) |
| Inference results per minute | 10 | 300 |
| Identity resolutions per minute | 10 | 300 |
| Sync items drained per minute | N/A | 60 |
| Routing decisions per minute | N/A | 100 |

---

## Reliability

| Requirement | Detail |
|-------------|--------|
| Dependency isolation | Services remain `/health` responsive when any dependency is down |
| Routing fallback | `POST /route` always returns a destination (never 503) |
| Kafka at-least-once | Consumer offsets committed only after successful processing |
| Outbox durability | `sync_outbox` persists until confirmed delivered; survives service restart |
| Identity idempotency | Reprocessing the same `InferenceResult` returns the same `edge_parcel_id` |
| Image best-effort | MinIO unavailability does not block inference or identity |

---

## Security

| Requirement | Detail |
|-------------|--------|
| No secrets in logs | Enforced by log scrubbing rules and code review |
| Secrets via environment | No hardcoded credentials in code or images |
| Metadata encryption | AES-256-GCM; key via `ENCRYPTION_KEY` env; versioned for rotation |
| Key rotation | `enc_key_version` tracks which key encrypted each row; rotation runbook in doc 02 |
| HTTPS in production | `CLOUD_SYNC_URL` and `ROUTING_API_URL` must use HTTPS; validated at startup |
| Non-root containers | All container processes run as `UID 1000`; no privileged mode |
| Privacy masking | Camera frames privacy-masked before any processing; no PII in Kafka payloads |
| Bearer token auth | Required in production (see API contracts); JWT validated at reverse proxy |

---

## Operability

| Requirement | Detail |
|-------------|--------|
| Health endpoints | All services expose `GET /health` → 200 `"ok"` |
| API docs | All edge-services roles expose `GET /docs` (OpenAPI/Swagger UI) |
| Metrics | `GET /metrics` on monitoring role; Prometheus scrape configured |
| Structured logging | JSON logs with `timestamp`, `level`, `service`, `message`, `trace_id` |
| Distributed tracing | OpenTelemetry trace propagation via HTTP headers; spans exported to collector |
| Alert thresholds | Defined in Observability Spec (doc 01) |
| Runbooks | All common failure modes documented in Deployment & Operations (doc 02) |

---

## Scalability

| Dimension | Scaling Approach |
|-----------|----------------|
| Camera streams | Add partitions to `frames` topic; deploy additional ingestion replicas |
| Inference throughput | Add replicas to `edge-services` (role=inference); GPU upgrade path available |
| Identity throughput | Add replicas; Kafka consumer group handles partition rebalancing |
| Storage | Postgres vertical scaling + read replicas; MinIO distributed mode |
| Vector index | Qdrant horizontal scaling via collection sharding |

---

## Compliance & Data Governance

| Requirement | Detail |
|-------------|--------|
| GDPR camera feeds | Privacy masking applied; no PII stored in Kafka, Qdrant, or Postgres |
| Data retention | Defined per table in Data Model Spec (doc 06) |
| Audit trail | `parcel_events` provides immutable event log per parcel |
| Right to erasure | `DELETE` from `parcels` cascades to `parcel_events`; manual Qdrant point deletion required |
| Data residency | All data stored on-premise edge host; cloud sync sends minimal parcel metadata only |

---

## Capacity Planning (Pilot Facility)

| Resource | Estimate | Basis |
|----------|---------|-------|
| Postgres storage (year 1) | ~50 GB | 1 M parcels × ~50 KB avg event payload |
| MinIO storage (year 1) | ~2 TB | 1 M images × ~2 MB avg |
| Qdrant storage (year 1) | ~3 GB | 1 M vectors × 768 × 4 bytes + overhead |
| Kafka disk (7-day retention) | ~100 GB | 300 frames/min × 15 MB avg × 1 h frames retention |
| CPU (inference, no GPU) | 4 cores dedicated | ~400 ms/frame × 5 concurrent |
| RAM (all services) | 16 GB total | Postgres 4 GB, Qdrant 4 GB, inference 4 GB, others 4 GB |
| GPU (optional) | 1 × NVIDIA T4 or better | 10× latency improvement for inference |
