# Acceptance Test Specification

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** QA + Edge Platform Engineering | **Review Cadence:** Per Release

---

## Test Environment Prerequisites

Before running any acceptance tests:

1. `docker-compose up -d` — all containers must be running.
2. All health checks pass: `./scripts/health_check.sh` exits 0.
3. Kafka topics `frames` and `inference_results` exist (auto-created on broker start).
4. Qdrant collection `parcel_fingerprints` reachable (auto-created by identity service).
5. Postgres schema applied via migration init container.
6. MinIO bucket `parcels` accessible (auto-created on first use).
7. Environment: `LOCAL_DEFAULT=dock-A` set; `CLOUD_SYNC_URL` optional.

**Script:** `./scripts/e2e.sh` — automated; exits 0 on full pass, non-zero with failing step printed.

---

## P0 — End-to-End Happy Path

**Timeout:** 60 seconds total (each step has individual timeout).

### Step 1 — Health Checks

| Check | Expected | Timeout |
|-------|---------|---------|
| `GET http://localhost:8081/health` | HTTP 200, body `"ok"` | 5 s |
| `GET http://localhost:8082/health` | HTTP 200, body `"ok"` | 5 s |
| `GET http://localhost:8083/health` | HTTP 200, body `"ok"` | 5 s |
| `GET http://localhost:8084/health` | HTTP 200, body `"ok"` | 5 s |
| `GET http://localhost:8085/health` | HTTP 200, body `"ok"` | 5 s |
| `GET http://localhost:8086/health` | HTTP 200, body `"ok"` | 5 s |

**Rollback on failure:** Fix failing service; re-run `docker-compose restart <service>`.

### Step 2 — Image Ingestion

```bash
POST http://localhost:8081/ingest
Content-Type: application/json
{ "camera_id": "cam-test", "image_base64": "<test_image_base64>" }
```

| Expected | Timeout |
|---------|---------|
| HTTP 202 | 2 s |
| Response body: `{ "status": "queued" }` | — |

### Step 3 — Kafka `frames` Topic

Poll `frames` topic with `--offset end`, retry up to 10 × 1 s.

| Expected | Timeout |
|---------|---------|
| Message appears with `image_base64` non-empty | 10 s |
| Message `camera_id` matches `"cam-test"` | — |
| Message `timestamp_ms` within 5 s of now | — |

### Step 4 — Kafka `inference_results` Topic

Poll `inference_results` topic, retry up to 20 × 1 s.

| Expected | Timeout |
|---------|---------|
| Message appears with `fingerprint` array of length 768 | 20 s |
| `detections` array present (may be empty) | — |
| `image_object_key` non-empty | — |
| `camera_id` matches `"cam-test"` | — |

### Step 5 — MinIO Image Storage

Retrieve `image_object_key` from Step 4 result.

| Expected | Timeout |
|---------|---------|
| `GET MinIO:{image_object_key}` returns 200 | 5 s |
| Content-Type is `image/jpeg` | — |
| Object size > 0 bytes | — |

### Step 6 — Postgres Persistence

Query Postgres after Step 4 completes; retry up to 10 × 1 s.

| Expected | Timeout |
|---------|---------|
| `SELECT count(*) FROM parcels WHERE camera_id='cam-test'` ≥ 1 | 10 s |
| Corresponding row in `parcel_events` with `event_type IN ('identified', 'new_identity')` | — |
| `sync_outbox` row with `status='pending'` exists | — |

### Step 7 — Sync Status

| Expected | Timeout |
|---------|---------|
| `GET http://localhost:8084/sync/status` returns `{ "pending": N }` where N ≥ 0 | 2 s |
| If `CLOUD_SYNC_URL` set: pending count decreases to 0 within 30 s | 30 s |

### Step 8 — Routing Decision

```bash
POST http://localhost:8085/route
{ "edge_parcel_id": "<edge_parcel_id from step 6>" }
```

| Expected | Timeout |
|---------|---------|
| HTTP 200 | 2 s |
| Response contains `destination` non-empty | — |
| Response contains `source` in `["local-rule", "cloud", "local-default"]` | — |
| No 5xx error in service logs for this request | — |

**Success Criteria:** All 8 steps pass; no `ERROR` or `FATAL` level log lines in any service during the test run.

---

## P1 — Sad Path / Negative Tests

### N-01 — Empty `image_base64`

```bash
POST http://localhost:8081/ingest
{ "camera_id": "cam-test", "image_base64": "" }
```

| Expected |
|---------|
| HTTP 400 |
| Response body contains `"error"` key |
| No message published to `frames` topic |

### N-02 — Missing `image_base64`

```bash
POST http://localhost:8081/ingest
{ "camera_id": "cam-test" }
```

| Expected |
|---------|
| HTTP 400 |
| Error message references `image_base64` |

### N-03 — Oversized Payload

```bash
POST http://localhost:8081/ingest
{ "image_base64": "<11 MB of base64>" }
```

| Expected |
|---------|
| HTTP 413 |

### N-04 — Route for Unknown Parcel

```bash
POST http://localhost:8085/route
{ "edge_parcel_id": "00000000-0000-0000-0000-000000000000" }
```

| Expected |
|---------|
| HTTP 200 (routing never fails) |
| `destination` equals `LOCAL_DEFAULT` value |
| `source` equals `"local-default"` |

### N-05 — Infer with Invalid Base64

```bash
POST http://localhost:8082/infer
{ "image_base64": "NOT_VALID_BASE64!!!" }
```

| Expected |
|---------|
| HTTP 422 |
| Error message references decode failure |

### N-06 — Health Checks During Dependency Outage

Simulate Postgres down: `docker-compose stop postgres`.

| Expected |
|---------|
| `GET /health` on all services returns HTTP 200 (services remain alive) |
| `POST /route` still returns HTTP 200 with `"local-default"` source |
| Restore: `docker-compose start postgres`; wait 30 s; verify normal operation resumes |

---

## Rollback Criteria

| Scenario | Action |
|----------|--------|
| Step 1 fails (service unhealthy) | `docker-compose restart <service>`; investigate logs; re-run |
| Step 2 fails (ingestion 503) | Check Kafka broker health; `docker-compose restart redpanda`; re-run |
| Step 4 timeout (no inference result) | Check inference service logs for ONNX or MinIO errors; re-run |
| Step 6 fails (no Postgres rows) | Check identity service logs for DB connection errors; re-run |
| P1 N-06 — services crash during outage | Service restart policy `on-failure` recovers automatically; verify within 60 s |

---

## Test Data

| Item | Value |
|------|-------|
| Test image | 640×480 JPEG; contains ≥ 1 rectangular parcel-like object |
| `camera_id` | `"cam-test"` (deterministic; avoids cross-contamination) |
| `LOCAL_DEFAULT` | `"dock-A"` |
| `FINGERPRINT_MATCH_THRESHOLD` | `0.85` (default) |
