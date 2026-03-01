# User Stories

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** Edge Platform PM | **Review Cadence:** Per Sprint**

---

## Sizing Key

| Size | Story Points | Scope |
|------|------------|-------|
| XS | 1 | < 1 day; single endpoint or field change |
| S | 2 | 1–2 days; single service change |
| M | 5 | 3–5 days; cross-service or new feature |
| L | 8 | 1–2 weeks; architectural or multi-service |

---

## Operator

### US-OP-01 — Service Health Verification
**As an** operator,
**I want to** verify that all edge services are healthy,
**so that** I can trust the edge runtime before starting a shift.

**Size:** XS | **Priority:** Must Have | **Linked Req:** FR-08, OR-07

**Acceptance Criteria:**
- Running the health-check script returns HTTP 2xx from ports 8081–8086.
- Script exits 0 if all checks pass; exits non-zero and prints failing service name on any failure.
- Health check completes within 10 s.
- Script output is human-readable (service name, status, latency ms).

---

### US-OP-02 — End-to-End Pipeline Validation
**As an** operator,
**I want to** run an automated end-to-end test,
**so that** I can confirm the full ingestion → routing pipeline is working before relying on it operationally.

**Size:** S | **Priority:** Must Have | **Linked Req:** FR-01 through FR-07, OR-07

**Acceptance Criteria:**
- Single command (`./scripts/e2e.sh`) triggers the full pipeline test.
- Script returns exit code 0 only when all 8 acceptance steps complete successfully.
- Any failure prints which step failed and the observed vs. expected value.
- Script completes within 60 s on a standard dev machine.

---

### US-OP-03 — Operator Dashboard Access
**As an** operator,
**I want to** open a dashboard showing the status of all edge services,
**so that** I can monitor system health without SSH access.

**Size:** S | **Priority:** Should Have | **Linked Req:** FR-09

**Acceptance Criteria:**
- Dashboard available at `http://localhost:3000`.
- Dashboard shows links to inference, identity, sync, routing, monitoring.
- Page loads in under 2 s on a local network.
- Links open in a new tab and resolve to the correct service.

---

## Edge Engineer

### US-ENG-01 — Image Ingestion Validation
**As an** edge engineer,
**I want to** POST an image to `/ingest` and observe it on the `frames` Kafka topic,
**so that** I can validate the ingestion path independently during development.

**Size:** XS | **Priority:** Must Have | **Linked Req:** FR-01

**Acceptance Criteria:**
- `POST /ingest` with `{ "camera_id": "cam-01", "image_base64": "<valid base64>" }` returns HTTP 202.
- A message appears on the `frames` topic within 2 s containing `image_base64` and matching `camera_id`.
- `POST /ingest` with empty or missing `image_base64` returns HTTP 400 with an error message.
- `POST /ingest` with non-base64 payload returns HTTP 400.

---

### US-ENG-02 — ML Pipeline Output Verification
**As an** edge engineer,
**I want** the `inference_results` topic to contain `detections` and `fingerprint` arrays,
**so that** I can evaluate the quality of the ML pipeline without running the full system.

**Size:** S | **Priority:** Must Have | **Linked Req:** FR-02

**Acceptance Criteria:**
- `inference_results` message contains `fingerprint[]` of length 768.
- `inference_results` message contains `detections[]`; may be empty if no object detected.
- Each detection contains `x1, y1, x2, y2, score, label`.
- If no detections, `fingerprint` is a zero vector (not null); pipeline continues.
- `image_object_key` is present and non-empty in all results.

---

### US-ENG-03 — MinIO Artifact Persistence
**As an** edge engineer,
**I want** the captured image to be stored in MinIO,
**so that** I can reference the original artifact for debugging and audit.

**Size:** XS | **Priority:** Must Have | **Linked Req:** FR-03

**Acceptance Criteria:**
- Object appears in MinIO bucket `parcels` under key matching `image_object_key` in `inference_results`.
- Object is retrievable via MinIO console or S3 API within 5 s of inference.
- If MinIO is temporarily unavailable, inference still produces `inference_results` (best-effort).
- Object key follows format `capture/{uuid}.jpg` when not provided by caller.

---

### US-ENG-04 — Direct Inference Endpoint
**As an** edge engineer,
**I want to** call `POST /infer` directly with an image or object key,
**so that** I can test the inference service in isolation without Kafka.

**Size:** XS | **Priority:** Must Have | **Linked Req:** FR-02

**Acceptance Criteria:**
- `POST /infer` with `image_base64` returns 200 with full `InferenceResult`.
- `POST /infer` with `object_key` loads image from MinIO and returns result.
- Response time under 3 s on CPU hardware.

---

## Data / ML Engineer

### US-ML-01 — Vector Linkage in Qdrant
**As a** data/ML engineer,
**I want** vectors in Qdrant to be linked to `edge_parcel_id`,
**so that** I can analyze identity performance and trace which parcel a vector belongs to.

**Size:** S | **Priority:** Must Have | **Linked Req:** FR-04

**Acceptance Criteria:**
- Each vector in collection `parcel_fingerprints` has payload `{ "edge_parcel_id": "<uuid>" }`.
- A new vector is inserted when `match_score` is below `FINGERPRINT_MATCH_THRESHOLD`.
- An existing vector is returned (no insert) when `match_score` is at or above threshold.
- `qdrant_point_id` in `parcels` table matches the Qdrant point ID.

---

### US-ML-02 — Match Threshold Configurability
**As a** data/ML engineer,
**I want** the identity match threshold to be configurable without code changes,
**so that** I can tune precision/recall tradeoffs in production without redeploying.

**Size:** XS | **Priority:** Should Have | **Linked Req:** FR-04, Constraints

**Acceptance Criteria:**
- `FINGERPRINT_MATCH_THRESHOLD` env var controls the threshold (float 0.0–1.0).
- Changing the value and restarting the service takes effect immediately.
- Default value is documented in deployment guide.

---

## Fleet Admin

### US-ADM-01 — Cloud Sync Outbox Drain
**As a** fleet admin,
**I want** the sync outbox to drain automatically to a configured cloud endpoint,
**so that** the central cloud registry stays up to date without manual intervention.

**Size:** S | **Priority:** Must Have | **Linked Req:** FR-06

**Acceptance Criteria:**
- Pending `sync_outbox` items are POSTed to `CLOUD_SYNC_URL` when configured.
- Items are marked `status = sent` with `sent_at` timestamp after HTTP 200 response.
- `/sync/status` returns `{ "pending": N }` reflecting current queue depth.
- If cloud endpoint returns non-200, item remains `pending`; retry on next poll cycle.
- If `CLOUD_SYNC_URL` is not set, items are marked `sent` locally (graceful degradation).

---

### US-ADM-02 — Per-Parcel Routing Rules
**As a** fleet admin,
**I want to** set routing rules per parcel,
**so that** I can direct specific parcels to designated destinations without code changes.

**Size:** S | **Priority:** Should Have | **Linked Req:** FR-10

**Acceptance Criteria:**
- `POST /route/rules` with `{ "edge_parcel_id": "...", "destination": "dock-A" }` persists the rule.
- `POST /route` for that parcel subsequently returns `destination: "dock-A"` with `source: "local-rule"`.
- Disabled rules (`enabled: false`) are ignored; fallback to cloud or default applies.
- Rule updates take effect within one request cycle (no cache invalidation delay beyond DB read).

---

### US-ADM-03 — Cloud Routing Override
**As a** fleet admin,
**I want** the routing service to fall back to a cloud API when no local rule exists,
**so that** centrally managed routing policies are honored at the edge.

**Size:** S | **Priority:** Should Have | **Linked Req:** FR-14

**Acceptance Criteria:**
- When `ROUTING_API_URL` is set and no local rule matches, `/route` calls the cloud API.
- Response `source` is `cloud` when cloud responds; `local-default` when cloud is unreachable.
- Cloud timeout does not hang `/route` beyond 2 s; fallback to `LOCAL_DEFAULT` applies.
- Cloud errors are logged but do not propagate as 5xx to the caller.

---

## SRE / On-Call

### US-SRE-01 — Prometheus Metrics Scrape
**As an** SRE,
**I want** all edge services to expose Prometheus metrics,
**so that** I can configure alerts and dashboards for production monitoring.

**Size:** S | **Priority:** Must Have | **Linked Req:** FR-11

**Acceptance Criteria:**
- `GET /metrics` on the monitoring service returns valid Prometheus text format.
- `gpu_utilization` gauge is present (value 0 if no GPU detected).
- Prometheus successfully scrapes the target (status `UP` in Prometheus UI).
- Grafana dashboard panels render without errors.

---

### US-SRE-02 — Structured Log Access
**As an** SRE,
**I want** container logs to be structured JSON,
**so that** I can ingest them into a log aggregation system and query by field.

**Size:** S | **Priority:** Must Have | **Linked Req:** OR-08, Observability Spec

**Acceptance Criteria:**
- Each log line is valid JSON with fields: `timestamp`, `level`, `service`, `message`, `trace_id` (when available).
- No secrets or credentials appear in any log line.
- Logs are accessible via `docker-compose logs <service>`.
- Log level is configurable via `LOG_LEVEL` env (DEBUG, INFO, WARNING, ERROR).
