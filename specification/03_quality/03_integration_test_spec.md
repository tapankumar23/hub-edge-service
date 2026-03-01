# Integration Test Specification

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** QA + Edge Platform Engineering | **Review Cadence:** Per Release

---

## Principles

- Each test exercises exactly one service boundary (one producer, one consumer, one store).
- Tests are isolated: unique `camera_id` / `edge_parcel_id` per test to avoid contamination.
- All tests run against live services via docker-compose; no in-process mocks for service boundaries.
- External cloud endpoints replaced by local WireMock mock server.
- Tests are idempotent: repeated runs produce consistent results.
- Coverage target: 100% of service-to-service interfaces in Functional Spec (doc 02).

---

## Environment Setup & Teardown

### Setup (Before All Integration Tests)

```bash
docker-compose up -d
./scripts/health_check.sh

# Start WireMock mock server
docker run -d --name wiremock --network edge-net -p 9099:8080 \
  wiremock/wiremock:latest

# Configure stubs (sync returns 200; routing returns dock-cloud)
./scripts/setup_wiremock_stubs.sh

# Seed a test routing rule
curl -s -X POST http://localhost:8085/route/rules \
  -H 'Content-Type: application/json' \
  -d '{"edge_parcel_id":"int-rule-001","destination":"dock-X"}'
```

### Teardown (After All Integration Tests)

```bash
docker stop wiremock && docker rm wiremock

psql "$DATABASE_URL" <<SQL
  DELETE FROM parcel_events WHERE payload->>'test_run' = 'integration';
  DELETE FROM parcels       WHERE camera_id LIKE 'int-test-%';
  DELETE FROM sync_outbox   WHERE created_at > now() - interval '1 hour';
  DELETE FROM routing_rules WHERE rule_name LIKE 'int-%';
SQL
```

---

## Test Cases

### IT-01 — Ingestion ↔ Kafka `frames`

**Boundary:** camera-ingestion → Kafka `frames`

**Setup:** Subscribe `--offset end` before triggering.

**Steps & Assertions:**

| Step | Command | Assertion |
|------|---------|-----------|
| 1 | `POST /ingest { camera_id: "int-test-cam-01", image_base64: "<test>" }` | HTTP 202 within 1 s |
| 2 | Poll `frames` with retry 10 × 500 ms | Message appears within 5 s |
| 3 | Inspect message | `camera_id == "int-test-cam-01"`, `image_base64` non-empty, `schema_version == 1` |

---

### IT-02 — Inference ↔ MinIO + Kafka `inference_results`

**Boundary:** edge-inference ← frames → MinIO + inference_results

**Steps & Assertions:**

| Step | Command | Assertion |
|------|---------|-----------|
| 1 | `POST /infer { image_base64: "<test>", camera_id: "int-test-cam-02" }` | HTTP 200 within 5 s |
| 2 | Inspect response | `fingerprint.length == 768`, `detections` array present, `image_object_key` non-empty |
| 3 | `GET MinIO:parcels/{image_object_key}` | HTTP 200, size > 0 |
| 4 | Poll `inference_results` with retry | Message appears within 10 s; matches assertions from step 2 |

---

### IT-03 — Identity ↔ Qdrant + Postgres

**Boundary:** edge-identity ← inference_results → Qdrant + Postgres

**Steps & Assertions:**

| Step | Command | Assertion |
|------|---------|-----------|
| 1 | `POST /identify { inference: <InferenceResult> }` | HTTP 200 within 5 s |
| 2 | Check `is_new` | `true` for new parcel; `false` for identical re-submission |
| 3 | Qdrant: `GET /collections/parcel_fingerprints/points/{qdrant_point_id}` | Point exists with `edge_parcel_id` payload |
| 4 | Postgres: `SELECT * FROM parcels WHERE edge_parcel_id = ?` | Row present |
| 5 | Postgres: `SELECT * FROM parcel_events WHERE edge_parcel_id = ?` | Row with `event_type IN ('identified','new_identity')` |
| 6 | Postgres: `SELECT * FROM sync_outbox WHERE status = 'pending'` | Row present within 5 s |

**Idempotency:** Call `/identify` twice with identical fingerprint; assert same `edge_parcel_id`; assert Qdrant point count unchanged.

---

### IT-04 — Sync ↔ Cloud (Mock)

**Boundary:** edge-sync → sync_outbox → WireMock

**Setup:** `CLOUD_SYNC_URL=http://wiremock:9099/sync`; WireMock returns 200.

**Steps & Assertions:**

| Step | Assertion |
|------|-----------|
| Seed pending row in `sync_outbox` | Row visible in `GET /sync/status` as `pending: 1` |
| Wait 30 s (poll cycle × 3) | Row status = `sent`; `sent_at` non-null |
| WireMock request log | Exactly 1 POST received with correct payload |

**Failure path:** Configure WireMock to return 500; assert row remains `pending` after 30 s; `retry_count` incremented.

---

### IT-05 — Routing ↔ Postgres (Local Rule)

**Boundary:** edge-routing ← routing_rules (Postgres)

| Step | Command | Assertion |
|------|---------|-----------|
| 1 | `POST /route/rules { edge_parcel_id: "int-rule-001", destination: "dock-X" }` | HTTP 200 `{ ok: true }` |
| 2 | `POST /route { edge_parcel_id: "int-rule-001" }` | HTTP 200 `{ destination: "dock-X", source: "local-rule" }` |

---

### IT-06 — Routing ↔ Cloud API (Mock)

**Boundary:** edge-routing → WireMock (ROUTING_API_URL)

**Setup:** `ROUTING_API_URL=http://wiremock:9099/route`; stub returns `{ destination: "dock-cloud" }`.

| Step | Command | Assertion |
|------|---------|-----------|
| 1 | `POST /route { edge_parcel_id: "int-unknown-parcel" }` | HTTP 200 `{ destination: "dock-cloud", source: "cloud" }` |

**Timeout path:** Stub adds 5 s delay (> 2 s routing timeout); assert response within 3 s with `source: "local-default"`.

---

### IT-07 — Observability

**Boundary:** Prometheus → edge-monitoring → Grafana

| Step | Assertion |
|------|-----------|
| `GET http://localhost:8086/metrics` | Valid Prometheus text format; `gpu_utilization` present |
| `GET http://localhost:9090/api/v1/targets` | `edge-services-monitoring` shows `UP` |
| `GET http://localhost:9090/api/v1/query?query=edge_sync_outbox_pending` | Numeric result returned |
| `GET http://localhost:3001/api/health` | HTTP 200 `{ database: ok }` |

---

### IT-08 — Key Rotation & Metadata Decryption

**Boundary:** identity service ↔ Postgres (encryption/decryption with key versioning)

**Purpose:** Verify that encryption keys can be rotated without data loss; old key versions decrypt successfully.

**Setup:**
```bash
# Initial state: ENCRYPTION_KEY=<key1_hex_32bytes>
# Create and encrypt a parcel with key v1
POST /identify { inference: <InferenceResult>, metadata: { routing_hint: "dock-A" } }

# Assert encrypted metadata exists
SELECT enc_key_version, metadata_enc FROM parcels WHERE edge_parcel_id = ?
# Expected: enc_key_version = 1, metadata_enc is not null
```

**Key Rotation Procedure:**

| Step | Command | Assertion |
|------|---------|-----------|
| 1 | Read `parcels` row; extract `enc_key_version = 1` | Version present |
| 2 | Generate new 32-byte hex key (`key2_hex`) | New key != old key |
| 3 | In `encryption_key_version` table, insert: `{ version: 2, key: key2_hex, created_at: now() }` | Row inserted |
| 4 | Update env: `ENCRYPTION_KEY=<key2_hex>` | Identity service reconfigured |
| 5 | Restart identity service: `docker-compose restart edge-services-identity` | Service offline, then online |
| 6 | Create new parcel via `/identify` with new key | `enc_key_version = 2` on new row |

**Decryption Verification:**

| Step | Command | Assertion |
|------|---------|-----------|
| 1 | Query old row (v1): `SELECT metadata_enc FROM parcels WHERE enc_key_version = 1 LIMIT 1` | Ciphertext present |
| 2 | Decrypt with old key in application layer: `decrypt_with_version(metadata_enc, key_version=1)` | Raw JSON returns `{ routing_hint: "dock-A" }` |
| 3 | Query new row (v2): `SELECT metadata_enc FROM parcels WHERE enc_key_version = 2 LIMIT 1` | Ciphertext present |
| 4 | Decrypt with new key: `decrypt_with_version(metadata_enc, key_version=2)` | Raw JSON decrypts correctly |
| 5 | Attempt decryption of v2 record with v1 key | Decryption fails (GCM auth tag invalid) |

**Implementation Notes:**
- Identity service maintains in-memory map: `key_version → key_bytes`.
- On startup, load `encryption_key_version` table and populate map.
- `encrypt()` uses current `ENCRYPTION_KEY` env and increments `enc_key_version`.
- `decrypt()` looks up version in map; raises error if version not found.
- Test uses direct SQL queries to verify ciphertext presence; decryption tested via Python/app-level calls.

---

## Mocking Strategy

| External Dependency | Tool | Scope |
|--------------------|------|-------|
| `CLOUD_SYNC_URL` | WireMock `:9099` | IT-04 |
| `ROUTING_API_URL` | WireMock `:9099` | IT-06 |
| MinIO (failure) | `docker-compose stop minio` | Failure-mode tests |
| Postgres (failure) | `docker-compose stop postgres` | Failure-mode tests |
| Qdrant (failure) | `docker-compose stop qdrant` | Failure-mode tests |

---

## CI/CD Integration

- Runs on every PR modifying service code or `docker-compose.yml`.
- GitHub Actions job `integration-tests`: starts full stack, runs tests, tears down.
- Tests must pass before merge to `main`.
- Test results in JUnit XML format for GitHub test summary.
- Coverage report uploaded as artifact.

---

## Coverage

| Interface | Test | Required |
|-----------|------|---------|
| camera-ingestion → frames | IT-01 | Yes |
| inference ← frames | IT-02 | Yes |
| inference → MinIO | IT-02 | Yes |
| inference → inference_results | IT-02 | Yes |
| identity ← inference_results | IT-03 | Yes |
| identity → Qdrant | IT-03 | Yes |
| identity → Postgres | IT-03 | Yes |
| identity → sync_outbox | IT-03 | Yes |
| sync → cloud | IT-04 | Yes |
| routing → Postgres | IT-05 | Yes |
| routing → cloud API | IT-06 | Yes |
| monitoring → Prometheus | IT-07 | Yes |
| identity → Postgres (encryption/decryption) | IT-08 | Yes |
