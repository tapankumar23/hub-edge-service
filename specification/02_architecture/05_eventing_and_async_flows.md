# Eventing & Async Flows

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** Edge Platform Engineering | **Review Cadence:** Per Release

---

## Kafka Broker — Redpanda

| Property | Dev | Production |
|----------|-----|-----------|
| Bootstrap servers | `redpanda:9092` | `redpanda:9092` (internal Docker) |
| Replication factor | 1 | 3 |
| Min ISR | 1 | 2 |
| Compression | none | lz4 |
| Schema Registry | None (JSON; schemas documented here) | Redpanda Schema Registry at `:8081` |

---

## Topics

### `frames`

| Property | Value |
|----------|-------|
| Partitions | 4 (scale by camera count; 1 partition per 2 cameras) |
| Replication factor | 1 dev / 3 prod |
| Retention | 1 hour (transient high-throughput; images are large) |
| Cleanup policy | `delete` |
| Partition key | `camera_id` (ensures per-camera ordering) |
| Max message size | 15 MB |
| Producer | `camera-ingestion` |
| Consumer group | `edge-inference-consumer` |
| DLQ topic | `frames.DLQ` |

**Producer config:**
```properties
acks=all
retries=5
retry.backoff.ms=200
max.in.flight.requests.per.connection=1
```

**Consumer config:**
```properties
group.id=edge-inference-consumer
auto.offset.reset=earliest
enable.auto.commit=false
max.poll.records=10
session.timeout.ms=30000
```

---

### `inference_results`

| Property | Value |
|----------|-------|
| Partitions | 4 |
| Replication factor | 1 dev / 3 prod |
| Retention | 24 hours |
| Cleanup policy | `delete` |
| Partition key | `camera_id` |
| Max message size | 2 MB (vectors only; no image bytes) |
| Producer | `edge-services` (role=inference) |
| Consumer group | `edge-identity-consumer` |
| DLQ topic | `inference_results.DLQ` |

**Producer config:**
```properties
acks=all
retries=5
retry.backoff.ms=200
```

**Consumer config:**
```properties
group.id=edge-identity-consumer
auto.offset.reset=earliest
enable.auto.commit=false
max.poll.records=5
session.timeout.ms=30000
```

---

### Dead Letter Queue Topics

| DLQ Topic | Source | Retention | Responder |
|-----------|--------|----------|----------|
| `frames.DLQ` | `frames` | 7 days | On-call SRE; manual triage |
| `inference_results.DLQ` | `inference_results` | 7 days | On-call SRE; manual triage |

**DLQ routing rule:** A message is DLQ'd after 3 consecutive non-recoverable processing failures (e.g., base64 decode error, model panic). Dependency-unavailability errors are retried via consumer restart, not DLQ'd.

**DLQ message envelope:**
```json
{
  "original_topic":     "frames",
  "original_partition": 2,
  "original_offset":    1042,
  "failure_reason":     "base64_decode_error",
  "failure_count":      3,
  "failed_at":          "2026-03-01T12:00:00Z",
  "original_payload":   "<original bytes, base64 encoded>"
}
```

---

## Schema Versioning

All messages include `"schema_version": 1` at the top level.

| Change Type | Breaking? | Strategy |
|-------------|----------|---------|
| Add optional field | No | Backward compatible; consumers ignore unknown fields |
| Add required field | Yes | Version bump; dual-produce during migration window |
| Remove field | Yes | Deprecate (keep sending) first; remove after all consumers updated |
| Change field type | Yes | New field name; deprecate old |
| Rename field | Yes | New field name + deprecate old |

---

## Async Flow Diagrams

### Ingestion → Inference → Identity

```
camera-ingestion     Kafka:frames    edge-inference    Kafka:inference_results    edge-identity
      │                   │                │                     │                      │
      │─ POST /ingest ───►│                │                     │                      │
      │                   │─ FrameEvent ──►│                     │                      │
      │                   │                │─ YOLO detect        │                      │
      │                   │                │─ MinIO.put_object   │                      │
      │                   │                │─ InferenceResult ──►│                      │
      │                   │                │                     │─ Qdrant search ──────►│
      │                   │                │                     │                      │─ Postgres insert
      │                   │                │                     │                      │─ sync_outbox insert
```

### Sync Drain Flow

```
sync-service               sync_outbox (Postgres)         cloud endpoint
      │                            │                            │
      │─ poll pending rows ────────►│                            │
      │◄── batch of pending rows ──│                            │
      │─ POST payload ─────────────────────────────────────────►│
      │◄── HTTP 200 ───────────────────────────────────────────│
      │─ UPDATE status='sent' ─────►│                            │
```

---

## Consumer Offset & Race Handling

| Scenario | Handling |
|----------|---------|
| Service restart mid-batch | `auto.commit=false`; offsets committed only after processing succeeds |
| Multiple consumers in same group | Kafka partitions assigned; each partition has exactly one consumer |
| Test CLI reads after producer | Use `--offset end` to follow new messages; use retry/backoff in test scripts |
| Rebalance during processing | Consumer rejoins; uncommitted offsets reprocessed (at-least-once semantics) |
| DLQ-bound message | Committed after DLQ write; original offset not reprocessed |

---

## Backpressure Handling

- `max.poll.records` limits in-flight work per consumer cycle; slow dependencies naturally throttle consumer.
- Kafka buffers upstream messages during downstream slowdown; topic retention ensures no message loss within retention window.
- Alert fires when `inference_results` consumer lag exceeds 500 messages (see Observability Spec).
- `session.timeout.ms=30000`: stalled consumer triggers rebalance after 30 s.

---

## Message Ordering Guarantees

- **Per-camera ordering guaranteed:** same `camera_id` → same partition → sequential processing.
- **Cross-camera ordering not guaranteed:** across partitions.
- **Identity service is idempotent:** duplicate messages result in the same `edge_parcel_id` (vector match returns existing point above threshold).
