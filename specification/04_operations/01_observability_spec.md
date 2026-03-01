# Observability Specification

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** SRE | **Review Cadence:** Quarterly

---

## Overview

Edge Hub observability consists of four pillars: **Metrics** (Prometheus), **Logs** (structured JSON), **Traces** (OpenTelemetry), and **Dashboards/Alerts** (Grafana + Alertmanager).

---

## SLI / SLO Definitions

| SLO | SLI | Target | Measurement Window |
|-----|-----|--------|-------------------|
| Ingestion availability | HTTP 2xx rate on `POST /ingest` | 99.9% | 30-day rolling |
| E2E latency | p50 time from ingest to `inference_results` | < 500 ms | 30-day rolling |
| Routing availability | HTTP 2xx rate on `POST /route` | 99.9% | 30-day rolling |
| Routing latency | p95 `POST /route` response time | < 200 ms | 30-day rolling |
| Sync lag | p95 `sent_at - created_at` for sync_outbox items | < 5 min | 30-day rolling |
| Service liveness | `GET /health` 2xx rate across all services | 99.9% | 30-day rolling |
| Pipeline error rate | DLQ message count per hour | < 1 msg/hour | Hourly |

**Error budget:** 0.1% error budget = 43 minutes/month downtime across critical services.

---

## Metrics

### Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: edge-services-monitoring
    static_configs:
      - targets: ['edge-services-monitoring:8086']
    scrape_interval: 15s
    scrape_timeout: 10s
  - job_name: postgres-exporter
    static_configs:
      - targets: ['postgres-exporter:9187']
  - job_name: redpanda
    static_configs:
      - targets: ['redpanda:9644']
```

### Metrics Catalog

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `gpu_utilization` | Gauge | `device` | GPU utilization 0.0–1.0; 0 if no GPU |
| `edge_frames_ingested_total` | Counter | `camera_id` | Total frames published to `frames` |
| `edge_inference_latency_seconds` | Histogram | `model_version`, `device` | ONNX decode + detect + embed duration |
| `edge_identity_match_score` | Histogram | — | Qdrant cosine match scores per resolution |
| `edge_identity_new_total` | Counter | — | New parcel identities created |
| `edge_identity_matched_total` | Counter | — | Existing parcel identities matched |
| `edge_sync_outbox_pending` | Gauge | `destination` | Current pending sync_outbox rows |
| `edge_sync_sent_total` | Counter | `destination` | Total sync items delivered to cloud |
| `edge_sync_failed_total` | Counter | `destination`, `reason` | Total sync items failed permanently |
| `edge_route_decisions_total` | Counter | `source` | Routing decisions by source (local-rule/cloud/local-default) |
| `edge_http_request_duration_seconds` | Histogram | `service`, `method`, `path`, `status_code` | HTTP request latency per endpoint |
| `edge_kafka_consumer_lag` | Gauge | `topic`, `consumer_group` | Current consumer lag per group/topic |
| `edge_minio_upload_duration_seconds` | Histogram | — | MinIO put_object duration |
| `edge_qdrant_search_duration_seconds` | Histogram | — | Qdrant search duration |

---

## Alert Rules

```yaml
# alerting_rules.yml
groups:
  - name: edge-hub-alerts
    rules:

      - alert: ServiceDown
        expr: up{job="edge-services-monitoring"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Edge monitoring service is down"
          runbook: "https://runbooks.internal/edge/service-down"

      - alert: HighInferenceLatency
        expr: histogram_quantile(0.95, edge_inference_latency_seconds_bucket) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Inference p95 latency > 2s for 5 minutes"
          runbook: "https://runbooks.internal/edge/high-inference-latency"

      - alert: KafkaConsumerLagHigh
        expr: edge_kafka_consumer_lag{topic="inference_results"} > 500
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "identity consumer lag > 500 messages"
          runbook: "https://runbooks.internal/edge/kafka-lag"

      - alert: SyncOutboxStale
        expr: edge_sync_outbox_pending > 0
          and on() (time() - max(sync_outbox_oldest_pending_timestamp) > 1800)
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Sync outbox has items pending > 30 minutes"
          runbook: "https://runbooks.internal/edge/sync-stale"

      - alert: DLQMessagesReceived
        expr: increase(kafka_consumer_group_records_consumed_total{topic=~".*\\.DLQ"}[1h]) > 0
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Messages arriving in DLQ topics"
          runbook: "https://runbooks.internal/edge/dlq-triage"

      - alert: HighErrorRate
        expr: |
          rate(edge_http_request_duration_seconds_count{status_code=~"5.."}[5m])
          / rate(edge_http_request_duration_seconds_count[5m]) > 0.01
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "HTTP error rate > 1% for 2 minutes"
          runbook: "https://runbooks.internal/edge/high-error-rate"

      - alert: EncryptionKeyMissing
        expr: edge_encryption_key_missing == 1
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "ENCRYPTION_KEY missing; metadata_enc disabled"
          runbook: "https://runbooks.internal/edge/encryption-key"
```

---

## Log Format (Structured JSON)

Every log line must be valid JSON with this schema:

```json
{
  "timestamp":  "2026-03-01T12:00:00.000Z",
  "level":      "INFO",
  "service":    "edge-identity",
  "message":    "parcel identified",
  "trace_id":   "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id":    "00f067aa0ba902b7",
  "camera_id":  "cam-01",
  "edge_parcel_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Field | Required | Description |
|-------|---------|-------------|
| `timestamp` | Yes | ISO 8601 UTC |
| `level` | Yes | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `service` | Yes | Service name (e.g., `edge-identity`) |
| `message` | Yes | Human-readable description; no secrets |
| `trace_id` | When available | W3C traceparent trace ID |
| `span_id` | When available | W3C traceparent span ID |
| Additional context | Optional | e.g., `camera_id`, `edge_parcel_id`, `match_score` |

**Prohibited in logs:** `ENCRYPTION_KEY`, `metadata_enc` raw value, `image_base64` (too large), any credential.

**Log levels by service event:**
| Event | Level |
|-------|-------|
| Request received | DEBUG |
| Successful processing | INFO |
| Dependency unavailable (service continues) | WARNING |
| Unexpected error (processing skipped) | ERROR |
| Critical failure (missing config, data corruption) | CRITICAL |

---

## Distributed Tracing (OpenTelemetry)

### Setup

- **SDK:** OpenTelemetry Python SDK (`opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-psycopg2`).
- **Exporter:** OTLP exporter → Jaeger (`:4317` gRPC) or Tempo (`:4317`).
- **Propagation:** W3C TraceContext (`traceparent` header).
- **Sampling:** 100% in dev; 10% in production (configurable via `OTEL_TRACES_SAMPLER_ARG`).

### Instrumented Spans

| Service | Span |
|---------|------|
| camera-ingestion | `ingest.validate`, `ingest.kafka_publish` |
| edge-inference | `inference.decode`, `inference.onnx_detect`, `inference.embed`, `inference.minio_put` |
| edge-identity | `identity.qdrant_search`, `identity.postgres_insert`, `identity.outbox_enqueue` |
| edge-sync | `sync.poll_outbox`, `sync.cloud_post` |
| edge-routing | `routing.db_lookup`, `routing.cloud_route` |

### Trace Propagation

Kafka messages include trace context in message headers (`traceparent`, `tracestate`) so traces span across topic boundaries.

---

## Grafana Dashboards

### Dashboard 1 — Edge Hub Overview

| Panel | Metric | Visualization |
|-------|--------|---------------|
| Service health | `up` per job | Status dots |
| Frames ingested/min | `rate(edge_frames_ingested_total[1m])` | Time series |
| E2E latency p50/p95 | `edge_inference_latency_seconds` histogram | Time series |
| Kafka consumer lag | `edge_kafka_consumer_lag` | Time series |
| Sync outbox pending | `edge_sync_outbox_pending` | Gauge |
| GPU utilization | `gpu_utilization` | Gauge |
| HTTP error rate | `rate(http_req{status_code=~"5.."}[5m])` | Time series |

### Dashboard 2 — Identity & Vector

| Panel | Metric | Visualization |
|-------|--------|---------------|
| New identities/min | `rate(edge_identity_new_total[1m])` | Time series |
| Match rate | `edge_identity_matched_total / (new + matched)` | Gauge |
| Match score distribution | `edge_identity_match_score` histogram | Heatmap |
| Qdrant search latency p95 | `edge_qdrant_search_duration_seconds` | Time series |

---

## Health & Docs Endpoints

| Service | `/health` | `/docs` | `/metrics` |
|---------|-----------|---------|-----------|
| camera-ingestion | Yes | No | No |
| edge-inference | Yes | Yes | No |
| edge-identity | Yes | Yes | No |
| edge-sync | Yes | Yes | No |
| edge-routing | Yes | Yes | No |
| edge-monitoring | Yes | Yes | Yes |

---

## On-Call & Escalation

| Severity | Response Time | Escalation Path |
|----------|--------------|----------------|
| Critical | 15 min | On-call SRE → Engineering Lead |
| Warning | 1 hour | On-call SRE |
| Info | Next business day | Engineering team |

Runbooks linked from each alert annotation. See [02_deployment_and_operations.md](02_deployment_and_operations.md) for full runbooks.
