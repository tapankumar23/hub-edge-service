# Edge Cases & Failure Modes

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** Edge Platform Engineering + SRE | **Review Cadence:** Quarterly

---

## Failure Mode Matrix

### Infrastructure Dependencies Down

| Dependency | Detection | Service Behavior | Recovery |
|-----------|-----------|-----------------|---------|
| **Postgres unreachable** | Connection timeout / refused | `/health` returns 200 (liveness preserved); identity skips writes; routing falls back to cloud/default | Auto-reconnect with exponential backoff (200 ms base, max 30 s); writes resume on reconnect |
| **Qdrant unreachable** | HTTP 5xx / connection error | Identity treats as new identity (no match); skips vector upsert; inserts Postgres row without qdrant_point_id | Auto-retry next message; Qdrant-less parcels flagged in `parcel_events` payload for backfill |
| **MinIO unavailable** | S3 SDK error | Inference skips `put_object`; `image_object_key` returned as `""`; downstream pipeline continues | Retry on next inference call; no backfill of missed uploads |
| **Kafka unavailable** | aiokafka/confluent exception | Producers queue locally (bounded buffer); consumers halt and retry reconnect; `/health` stays OK | Exponential backoff reconnect; messages in Kafka buffer delivered once broker resumes |
| **Redpanda leader election** | Temporary partition unavailability | Producers retry with `retries=5`, `retry.backoff.ms=200`; brief delay acceptable | Automatic; Kafka client handles leader re-election transparently |
| **Redis unavailable** | Connection refused | Redis is reserved; no current services depend on it; no impact | N/A |

---

### Circuit Breaker Configuration

Applied to outbound HTTP calls in sync and routing services:

| Service | Dependency | Open Threshold | Half-Open After | Fallback |
|---------|-----------|---------------|----------------|---------|
| sync | `CLOUD_SYNC_URL` | 5 consecutive 5xx in 60 s | 120 s | Leave rows `pending`; retry next poll cycle |
| routing | `ROUTING_API_URL` | 3 consecutive failures in 30 s | 60 s | Return `LOCAL_DEFAULT` immediately |
| identity | Qdrant HTTP | 3 consecutive failures | 30 s | Skip vector search; treat as new identity |
| identity | Postgres | 3 consecutive failures | 30 s | Skip all DB writes; log critical error |

**Circuit breaker library:** Use `tenacity` (Python) or equivalent. Log state transitions at WARN level.

---

### Retry Policies

| Component | Retry Strategy | Max Attempts | Backoff |
|-----------|---------------|-------------|--------|
| Kafka producer | Automatic (Kafka client) | 5 | 200 ms exponential |
| Kafka consumer reconnect | Manual with sleep | Indefinite | 5 s fixed |
| Sync cloud POST | Poll-based (next cycle) | Indefinite (until sent/failed) | 10 s poll interval |
| Routing cloud API | No retry | 1 (hard timeout) | 2 s timeout → fallback |
| Qdrant HTTP | `tenacity` | 3 | 500 ms exponential |
| Postgres connection | `psycopg2` reconnect | 3 | 1 s exponential |
| MinIO upload | None (best-effort) | 1 | N/A |

---

### Data Anomalies

| Anomaly | Detection | Behavior | Resolution |
|---------|-----------|---------|-----------|
| Empty `image_base64` | Input validation | `POST /ingest` → HTTP 400; no Kafka publish | Client corrects and retries |
| Invalid base64 encoding | Decode error | Inference service: log error; DLQ message after 3 failures | Manual DLQ triage |
| Oversized payload (> 10 MB) | Content-Length check | `POST /ingest` → HTTP 413 | Client resizes image |
| No YOLO detections | ONNX returns empty list | `fingerprint` set to zero vector (768 zeros); pipeline proceeds | Downstream: low match_score; creates new identity; logged at DEBUG |
| Zero vector fingerprint | Post-inference check | Qdrant cosine similarity against zeros is unreliable; logged at WARN | Use FINGERPRINT_MATCH_THRESHOLD appropriately; expect more new_identity events |
| Duplicate `inference_results` message | Kafka at-least-once | Identity service: second call returns same `edge_parcel_id` (vector match above threshold) | Idempotent by design |
| Corrupted ONNX model | ONNX runtime exception | Inference returns empty detections + zero fingerprint; logs CRITICAL; alert fires | Redeploy inference service with correct model; rollback procedure in doc 02 |
| Missing `ENCRYPTION_KEY` | Env check at startup | Identity service: logs CRITICAL; `metadata_enc` set to NULL; raw metadata never stored/logged | Set env var; restart service |
| `ENCRYPTION_KEY` rotation | Key version mismatch on read | Old rows unreadable with new key; `enc_key_version` column identifies affected rows | Follow key rotation runbook (doc 02) |

---

### Operational Races

| Race Condition | Context | Handling |
|---------------|---------|---------|
| CLI reads `frames` after inference consumes | Kafka consumer advances offset | Use `--offset end` before triggering; use retry/backoff in test scripts (E2E script does this) |
| Multiple identity service replicas processing same message | Kafka partitioning | Same `camera_id` → same partition → same consumer; single consumer per partition within a group |
| Sync service processes same outbox row twice | Double-poll bug | `UPDATE ... WHERE status='pending' RETURNING id` with row-level locking prevents double-processing |
| Routing rule update mid-request | DB read in request handler | DB read is transactionally isolated; rule takes effect on next request after commit |
| Qdrant collection creation race (two identity instances) | Both detect missing collection | Qdrant `create_collection` is idempotent; second call is ignored |

---

### Security Failure Modes

| Failure | Detection | Response |
|---------|-----------|---------|
| `ENCRYPTION_KEY` missing | Startup env check | Log CRITICAL; set `metadata_enc = NULL`; do not expose raw metadata; alert on-call |
| `ENCRYPTION_KEY` compromised | External detection | Follow key rotation runbook immediately; re-encrypt affected rows with new key version |
| Secrets in logs | Log scanning CI job | Build fails; secrets must be removed before merge |
| Invalid JWT token | Reverse proxy / auth middleware | HTTP 401; request rejected before reaching service |
| Cloud sync to HTTP (not HTTPS) | Startup config validation | Warn in dev; error in production; block startup if `CLOUD_SYNC_URL` uses plain HTTP in prod mode |

---

## Chaos Engineering Scenarios

For quarterly chaos testing (see Performance Test Spec doc 04):

| Scenario | Method | Expected Behavior | Pass Criteria |
|----------|--------|------------------|---------------|
| Kill Postgres mid-test | `docker-compose stop postgres` | Services remain healthy; routing uses fallback | All `/health` return 200; `/route` still responds within 2 s |
| Kill Qdrant mid-test | `docker-compose stop qdrant` | Identity treats all parcels as new | Identity continues processing; no crashes |
| Kill Redpanda mid-test | `docker-compose stop redpanda` | Consumers halt gracefully; producers queue | Services remain alive; Kafka reconnects within 30 s of broker return |
| Kill MinIO mid-test | `docker-compose stop minio` | Inference skips upload; pipeline continues | `image_object_key` is empty string; no 5xx errors from inference |
| Network partition (simulate) | `docker network disconnect edge-net <container>` | Affected service degrades gracefully | Circuit breaker opens; fallback activates within configured threshold |
| OOM (simulate via limits) | Set `--memory=64m` on inference container | Container OOM killed; Docker restarts it | Service recovers within `restart: on-failure` policy; no data loss |

---

## Partial Failure Rollback Procedures

See [02_deployment_and_operations.md](02_deployment_and_operations.md) for detailed runbooks.

| Scenario | Immediate Action |
|----------|----------------|
| ONNX model corruption | `docker-compose restart edge-services-inference`; if fails, `docker pull <prev-image>` |
| Postgres migration failure | Roll back via `./scripts/db_rollback.sh V<version>`; restore from backup if needed |
| Kafka topic corruption | Recreate topic (data loss within retention window); verify consumer group offsets |
| Qdrant data corruption | Restore from daily snapshot; re-embed affected parcels via backfill job |
