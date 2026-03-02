# Deployment & Operations

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** SRE | **Review Cadence:** Quarterly

---

## Environment Variables Reference

### Required (All Environments)

| Variable | Service | Description | Example |
|----------|---------|-------------|---------|
| `DATABASE_URL` | identity, sync, routing | Postgres connection string | `postgresql://user:pass@postgres:5432/edgehub` |
| `KAFKA_BOOTSTRAP_SERVERS` | ingestion, inference, identity | Redpanda broker address | `redpanda:9092` |
| `MINIO_ENDPOINT` | inference | MinIO API endpoint | `http://minio:9000` |
| `MINIO_ACCESS_KEY` | inference | MinIO access key | (secret) |
| `MINIO_SECRET_KEY` | inference | MinIO secret key | (secret) |
| `QDRANT_HOST` | identity | Qdrant HTTP host | `qdrant` |
| `QDRANT_PORT` | identity | Qdrant HTTP port | `6333` |
| `ENCRYPTION_KEY` | identity | AES-256-GCM encryption key (32 bytes hex) | (secret) |
| `LOCAL_DEFAULT` | routing | Default routing destination when no rule matches | `dock-A` |
| `ROLE` | edge-services | Service role: inference/identity/sync/routing/monitoring | `inference` |

### Optional

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `CAMERA_ID` | ingestion | `unknown` | Camera identifier for capture loop |
| `CLOUD_SYNC_URL` | sync | (none) | Cloud endpoint for sync outbox drain |
| `ROUTING_API_URL` | routing | (none) | Cloud routing API URL |
| `FINGERPRINT_MATCH_THRESHOLD` | identity | `0.85` | Cosine similarity threshold for match |
| `SYNC_POLL_INTERVAL_SECONDS` | sync | `10` | Outbox poll interval |
| `SYNC_BATCH_SIZE` | sync | `10` | Max rows per sync poll cycle |
| `LOG_LEVEL` | all | `INFO` | Logging level: DEBUG/INFO/WARNING/ERROR |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | all | (none) | OpenTelemetry collector gRPC endpoint |
| `OTEL_TRACES_SAMPLER_ARG` | all | `1.0` | Trace sampling ratio (1.0 = 100%) |
| `NEXT_PUBLIC_INFERENCE_URL` | dashboard | `http://localhost:8082` | Inference service public URL |
| `NEXT_PUBLIC_IDENTITY_URL` | dashboard | `http://localhost:8083` | Identity service public URL |
| `NEXT_PUBLIC_SYNC_URL` | dashboard | `http://localhost:8084` | Sync service public URL |
| `NEXT_PUBLIC_ROUTING_URL` | dashboard | `http://localhost:8085` | Routing service public URL |
| `NEXT_PUBLIC_MONITORING_URL` | dashboard | `http://localhost:8086` | Monitoring service public URL |

---

## Deployment Procedures

### Initial Deployment (First Time)

```bash
# 1. Clone repository
git clone <repo-url> && cd hub-edge-service

# 2. Copy and configure environment
cp .env.example .env
# Edit .env: set DATABASE_URL, MINIO_*, ENCRYPTION_KEY, LOCAL_DEFAULT, CLOUD_SYNC_URL

# 3. Start all services
docker-compose up -d

# 4. Verify health
./scripts/health_check.sh

# 5. Run P0 E2E test
./scripts/e2e.sh
```

### Rolling Update (Existing Deployment)

```bash
# 1. Pull new images
docker-compose pull

# 2. Restart services one at a time (zero-downtime for stateless services)
docker-compose up -d --no-deps camera-ingestion
docker-compose up -d --no-deps edge-services-inference
docker-compose up -d --no-deps edge-services-identity
docker-compose up -d --no-deps edge-services-sync
docker-compose up -d --no-deps edge-services-routing
docker-compose up -d --no-deps edge-services-monitoring
docker-compose up -d --no-deps ui-dashboard

# 3. Verify health after each restart
./scripts/health_check.sh

# 4. Run P0 E2E test
./scripts/e2e.sh
```

### Database Migration

```bash
# Run migration (idempotent; safe to run multiple times)
docker-compose run --rm db-migrate

# Verify migration applied
docker-compose exec postgres psql -U edgehub -c "\dt"

# Rollback (if needed)
./scripts/db_rollback.sh V002  # Roll back to version V002
```

### ENCRYPTION_KEY Rotation

```bash
# 1. Generate new key
NEW_KEY=$(openssl rand -hex 32)

# 2. Update .env with new key; keep old key as ENCRYPTION_KEY_OLD temporarily
echo "ENCRYPTION_KEY=$NEW_KEY" >> .env
echo "ENCRYPTION_KEY_OLD=$OLD_KEY" >> .env

# 3. Run re-encryption job (reads with old key, writes with new key)
docker-compose run --rm re-encrypt-job

# 4. Verify all rows now have enc_key_version = new_version
docker-compose exec postgres psql -U edgehub -c \
  "SELECT enc_key_version, count(*) FROM parcels GROUP BY enc_key_version;"

# 5. Remove ENCRYPTION_KEY_OLD from .env; restart services
docker-compose up -d
```

---

## Runbooks

### RB-01 — Service Not Starting

```
Symptom: Service container exits immediately or restarts repeatedly.

1. Check logs:
   docker-compose logs <service> --tail=50

2. Common causes:
   - Missing env var: look for "required env var not set" in logs
   - DB connection failure: verify DATABASE_URL and postgres health
   - Kafka unreachable: verify KAFKA_BOOTSTRAP_SERVERS and redpanda health

3. Fix:
   - Update .env with missing/corrected value
   - docker-compose restart <service>
   - Recheck health: ./scripts/health_check.sh
```

### RB-02 — Kafka Consumer Lag > 500 Messages

```
Symptom: Alert "KafkaConsumerLagHigh" fires.

1. Check current lag:
   docker-compose exec redpanda rpk group describe edge-identity-consumer

2. Check identity service logs for errors:
   docker-compose logs edge-services-identity --tail=100

3. Common causes:
   a. Qdrant slow/down → identity consumer stalls
   b. Postgres slow/down → identity consumer stalls
   c. CPU overload on inference → high produce rate

4. Fix (Qdrant/Postgres down):
   - Restart affected dependency
   - Consumer catches up automatically

5. Fix (CPU overload):
   - Scale inference replicas (if infrastructure allows)
   - Temporarily reduce camera frame rate
```

### RB-03 — Sync Outbox Stale (Items Pending > 30 Minutes)

```
Symptom: Alert "SyncOutboxStale" fires.

1. Check sync service status:
   curl http://localhost:8084/sync/status

2. Check sync logs:
   docker-compose logs edge-services-sync --tail=50

3. Common causes:
   a. CLOUD_SYNC_URL not set → items marked sent locally (check if this is intentional)
   b. Cloud endpoint returning 5xx → items remain pending
   c. Network connectivity loss to cloud

4. Diagnose cloud endpoint:
   curl -X POST $CLOUD_SYNC_URL -H 'Content-Type: application/json' \
     -d '{"test":true}'

5. Fix (cloud down):
   - Wait for cloud recovery; items will drain automatically
   - If prolonged: notify Fleet Admin; items safe in outbox up to 30-day retention

6. Fix (connectivity):
   - Check firewall/proxy settings; verify HTTPS certificate validity
```

### RB-04 — DLQ Messages Received

```
Symptom: Alert "DLQMessagesReceived" fires.

1. Consume DLQ to inspect:
   docker-compose exec redpanda rpk topic consume frames.DLQ --num 5

2. Inspect failure_reason in envelope.

3. Common failure reasons:
   a. base64_decode_error → malformed client; reject at source
   b. onnx_runtime_error → model issue; check model file integrity
   c. schema_version_unknown → client sending unsupported schema version

4. Fix:
   a. Identify and fix upstream client sending malformed messages
   b. For onnx errors: docker-compose restart edge-services-inference
      and verify model file: docker-compose exec edge-services-inference ls -la /models/

5. DLQ messages are NOT automatically replayed. Manual replay if needed:
   ./scripts/replay_dlq.sh frames.DLQ
```

### RB-05 — ONNX Model Corruption or Update

```
Symptom: Inference returning all-zero fingerprints; CRITICAL logs in inference service.

1. Verify model file:
   docker-compose exec edge-services-inference \
     python3 -c "import onnxruntime; sess=onnxruntime.InferenceSession('/models/yolo.onnx'); print('OK')"

2. If corrupt: pull clean image with correct model baked in:
   docker-compose pull edge-services-inference
   docker-compose up -d --no-deps edge-services-inference

3. Verify recovery:
   curl -X POST http://localhost:8082/infer \
     -H 'Content-Type: application/json' \
     -d "{ \"image_base64\": \"$TEST_IMAGE\" }"
   # Expect: detections array, fingerprint length 768
```

### RB-06 — Postgres Connection Exhaustion

```
Symptom: "too many connections" errors in service logs; DB operations failing.

1. Check active connections:
   docker-compose exec postgres psql -U edgehub -c \
     "SELECT count(*) FROM pg_stat_activity;"

2. Typical limit: 100 connections. Each service holds a pool.

3. Immediate relief: Restart services (releases connection pools):
   docker-compose restart edge-services-identity edge-services-sync edge-services-routing

4. Long-term fix: Add PgBouncer as connection pooler; update DATABASE_URL to point to PgBouncer.
```

---

## Incident Response

### Severity Classification

| Severity | Definition | Example |
|----------|-----------|---------|
| P1 — Critical | Full pipeline down; no parcels being processed | Kafka down; Postgres corrupted |
| P2 — Major | Degraded throughput or accuracy; some parcels lost | Qdrant down; MinIO down |
| P3 — Minor | Single service degraded; workaround available | Dashboard down; GPU unavailable |
| P4 — Low | Cosmetic or non-blocking issue | Grafana panel not rendering |

### Incident Response Steps

```
1. Acknowledge alert in PagerDuty (within 15 min for P1/P2).

2. Assess scope:
   ./scripts/health_check.sh
   docker-compose ps
   docker-compose logs --tail=50 <failing-service>

3. Identify root cause using runbooks above.

4. Apply fix or escalate.

5. Verify recovery:
   ./scripts/health_check.sh
   ./scripts/e2e.sh

6. Write incident post-mortem within 48 hours (template in wiki).
```

---

## On-Call Rotation

| Role | Responsibility | Contact |
|------|---------------|---------|
| Primary SRE | First responder for all P1/P2 alerts | PagerDuty rotation |
| Secondary SRE | Backup if primary unresponsive > 15 min | PagerDuty escalation |
| Engineering Lead | Escalation for data corruption or breaking changes | Direct contact |
| Fleet Admin | Escalation for cloud sync/routing issues | Direct contact |

**PagerDuty integration:** Alertmanager → PagerDuty via webhook. All Critical/Warning alerts route to on-call.

---

## Monitoring Quicklinks

| Tool | URL | Purpose |
|------|-----|---------|
| Grafana | http://localhost:3001 | Dashboards |
| Prometheus | http://localhost:9090 | Metrics queries |
| Kafka UI | http://localhost:8087 | Topic / consumer group inspection |
| MinIO Console | http://localhost:9001 | Object storage browser |
| Qdrant UI | http://localhost:6334/dashboard | Vector collection inspector |
