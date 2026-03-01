# Business Requirements

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** Edge Platform PM | **Review Cadence:** Quarterly

---

## MoSCoW Priority Legend

| Priority | Meaning |
|----------|---------|
| **M** — Must Have | Required for launch; blocking |
| **S** — Should Have | High value; include if feasible |
| **C** — Could Have | Nice-to-have; deferred if needed |
| **W** — Won't Have | Explicitly out of scope for this release |

---

## Core Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|------------|---------|-------------------|
| FR-01 | Ingest images from cameras or HTTP POST `/ingest`; produce `FrameEvent` to Kafka `frames` topic | **M** | POST returns 202; message visible in `frames` within 1 s |
| FR-02 | Run YOLO ONNX object detection on frames; produce `InferenceResult` to `inference_results` topic | **M** | `detections[]` and `fingerprint[]` present in result |
| FR-03 | Persist captured image to MinIO under `capture/{uuid}.jpg` | **M** | Object retrievable from MinIO immediately after inference |
| FR-04 | Resolve parcel identity via Qdrant cosine nearest-neighbor search | **M** | New parcel upserted when score below threshold; existing parcel matched when above |
| FR-05 | Persist `parcels` and `parcel_events` rows in Postgres for every identified parcel | **M** | Rows present within 5 s of ingestion |
| FR-06 | Enqueue sync item in `sync_outbox`; drain to `CLOUD_SYNC_URL` on 200 response | **M** | Items marked `sent` after cloud acknowledgement |
| FR-07 | Provide local routing decisions via `POST /route`; fall back to `LOCAL_DEFAULT` | **M** | Response always contains `destination`; source indicates decision origin |
| FR-08 | All services expose `/health` returning 2xx; inference/identity/sync/routing/monitoring expose `/docs` | **M** | Health checks pass in automated service-check scripts |
| FR-09 | Operator dashboard (Next.js) links to all services and shows system status | **S** | Dashboard loads within 2 s; all service links resolve |
| FR-10 | `/route/rules` endpoint allows admin-defined per-parcel routing rules | **S** | Rule persisted; subsequent `/route` for that parcel returns `local-rule` source |
| FR-11 | Monitoring service exposes Prometheus `/metrics` with `gpu_utilization` gauge | **M** | Prometheus scrapes successfully; gauge present (0 if no GPU) |
| FR-12 | Metadata encrypted at rest using `ENCRYPTION_KEY`; stored in `metadata_enc` column | **M** | Field encrypted; raw value never logged |
| FR-13 | Camera capture loop (optional) ingests frames from physical camera via gocv | **C** | Loop starts when `CAMERA_ID` env is set; frames appear in topic |
| FR-14 | Cloud routing override via `ROUTING_API_URL` when local rule absent | **S** | Cloud source returned when mock configured; fallback to `LOCAL_DEFAULT` on cloud error |
| FR-15 | Classify parcel damage (none/minor/major) from detected objects; return confidence score | **S** | Damage classification present in `InferenceResult`; confidence ≥ 0.75 threshold; linked to parcel record |

---

## Operational Requirements

| ID | Requirement | Priority |
|----|------------|---------|
| OR-01 | All services must start cleanly with `docker-compose up`; no manual init steps beyond env configuration | **M** |
| OR-02 | Kafka topics `frames` and `inference_results` created automatically on broker startup | **M** |
| OR-03 | MinIO bucket `parcels` created automatically on first use | **M** |
| OR-04 | Postgres schema applied via migration before services start | **M** |
| OR-05 | Qdrant collection `parcel_fingerprints` created automatically if absent | **M** |
| OR-06 | Services gracefully handle dependency unavailability without crashing | **M** |
| OR-07 | P0 E2E test script runnable as a single command; exits non-zero on failure | **M** |
| OR-08 | Services log structured JSON to stdout; no secrets in logs | **M** |
| OR-09 | GPU is optional; CPU fallback is automatic via ONNX Runtime | **M** |
| OR-10 | Grafana datasource pre-provisioned; dashboards importable from JSON | **S** |

---

## Security & Compliance Requirements

| ID | Requirement | Priority | Notes |
|----|------------|---------|-------|
| SC-01 | No credentials or secrets in container logs or Kafka topic payloads | **M** | Enforced by code review + log scanning |
| SC-02 | All secrets injected via environment variables; no hardcoded credentials | **M** | Secrets management via env or vault integration |
| SC-03 | `metadata_enc` encrypted using AES-256-GCM or equivalent; key via `ENCRYPTION_KEY` env | **M** | Key rotation runbook required |
| SC-04 | Cloud sync (`CLOUD_SYNC_URL`) uses HTTPS in production; plain HTTP only in dev/local | **M** | Enforced by config validation |
| SC-05 | Camera feeds must apply privacy masking before any downstream processing | **M** | GDPR compliance; faces/identifiable features blurred |
| SC-06 | No PII stored in Kafka topic payloads or vector embeddings | **M** | Embeddings represent parcel shape/texture, not persons |
| SC-07 | ENCRYPTION_KEY must be rotatable without data loss; versioning metadata required | **S** | Key version stored alongside ciphertext |
| SC-08 | API endpoints do not require auth in dev; bearer token auth required in production | **S** | See API contracts for security scheme |

---

## Non-Goals (Explicit Out-of-Scope)

- Real-time PII identification or facial recognition from camera feeds.
- Full warehouse management system (WMS) integration or replacement.
- Sub-100 ms inference latency (edge CPU constraint in initial release).
- Multi-tenancy across unrelated logistics operators.
- Direct PLC/conveyor control integration.
- Offline model training on edge hardware.

---

## Constraints

| Constraint | Detail |
|-----------|--------|
| Runtime | Docker Compose on a single edge host; no Kubernetes required for dev/initial prod |
| GPU | Optional; CPU fallback must be available |
| ML thresholds | Configurable via env; defaults tuned for demo quality; production calibration required before go-live |
| Network | Services communicate on internal Docker network; only listed ports exposed to host |
| Storage | MinIO must be persistent-volume backed in production |
| Database | Postgres 15+; schema migration required before first run |
