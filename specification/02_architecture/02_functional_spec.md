# Functional Specification

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** Edge Platform Engineering | **Review Cadence:** Per Release

---

## Parcel Lifecycle State Machine

```
[INGESTED] → (inference) → [DETECTED] → (identity search) → [IDENTIFIED or NEW]
     → (sync enqueue) → [PENDING_SYNC] → (sync drain) → [SYNCED]
     → (routing request) → [ROUTED]
```

State transitions are recorded as `parcel_events` rows with `event_type` values: `identified`, `new_identity`, `sync_enqueued`, `sync_sent`, `routed`.

---

## Service: camera-ingestion (port 8081)

### Inputs
- HTTP `POST /ingest` with body `{ "camera_id"?: string, "image_base64": string }`.
- Optional: background camera capture loop when `CAMERA_ID` env is set (gocv/OpenCV).

### Processing
1. Validate `image_base64` is non-empty; return HTTP 400 with `{ "error": "image_base64 required" }` if missing or empty.
2. Assign `camera_id` from request or fall back to `CAMERA_ID` env or `"unknown"`.
3. Build `FrameEvent`: `{ camera_id, timestamp_ms: now(), image_base64 }`.
4. Publish to Kafka topic `frames` using async producer; apply at-least-once delivery.

### Outputs
- HTTP 202 `{ "status": "queued" }` on success.
- HTTP 400 `{ "error": "<reason>" }` on validation failure.
- HTTP 503 if Kafka producer cannot connect after initial retry budget (5 attempts, 200 ms backoff).
- `GET /health` returns HTTP 200 `"ok"` always; Kafka connectivity is a liveness detail, not readiness gate.

### Timeouts & Retries
- Kafka publish timeout: 5 s per message.
- Kafka reconnect: exponential backoff, 200 ms base, max 30 s, indefinitely.

### Error Handling
| Condition | Behavior |
|-----------|---------|
| Empty `image_base64` | Return 400 |
| Kafka unavailable | Log error; return 503 with `{ "error": "upstream unavailable" }` |
| Oversized payload (> 10 MB) | Return 413 |
| Camera capture failure (loop) | Log warning; skip frame; continue loop |

---

## Service: edge-services — role=inference (port 8082)

### Inputs
- Kafka topic `frames` (consumer group: `edge-inference-consumer`).
- Optional: `POST /infer` with `{ "image_base64"?: string, "object_key"?: string, "camera_id"?: string }`.

### Processing
1. Decode base64 image (or load from MinIO if `object_key` provided).
2. Run YOLO ONNX detection: produce `detections[]` with `x1, y1, x2, y2, score, label`.
3. If no detections, set `fingerprint` to zero vector of length 768; continue pipeline.
4. Embed first detection bounding-crop into 768-dim fingerprint vector using embedding model.
5. **Classify parcel damage:** Run damage classifier on bounding-box crop of first detection. Produce `damage_classification` with `type: "none" | "minor" | "major"` and `confidence: float` (0.0–1.0). Include only if confidence ≥ `DAMAGE_CONFIDENCE_THRESHOLD` (default 0.75); otherwise omit field.
6. Store original image to MinIO bucket `parcels` under `capture/{uuid}.jpg` (skip if `object_key` already provided).
7. Publish `InferenceResult` to topic `inference_results`.

### Outputs
- `InferenceResult` to Kafka topic `inference_results`.
- `POST /infer` direct response: `InferenceResult` JSON.
- `GET /health` → 200 `"ok"`.
- `GET /docs` → OpenAPI docs.

### Timeouts & Retries
- ONNX inference timeout: 10 s (CPU); 3 s (GPU).
- MinIO upload timeout: 5 s; on failure, log warning and continue (best-effort).
- Kafka produce timeout: 5 s.

### Error Handling
| Condition | Behavior |
|-----------|---------|
| Invalid base64 | Log error; skip message (no DLQ publish for malformed data) |
| ONNX runtime error | Log error; publish result with empty `detections[]` and zero `fingerprint` |
| MinIO unavailable | Log warning; skip upload; `image_object_key` returns empty string |
| Kafka consumer disconnect | Reconnect with backoff; no message loss (at-least-once) |
| Damage classifier unavailable | Log warning; omit `damage_classification` from result; continue pipeline |

### Damage Classification Model

**Purpose:** Detect and classify parcel damage (physical wear, torn packaging, etc.) from detection bounding-box crops.

**Model Details:**
- Model type: Lightweight Convolutional Neural Network (CNN) or ViT-small.
- Input: RGB image crop (bounding box from YOLO detection); minimum 64×64 pixels.
- Output: Class logits for `["none", "minor", "major"]` → softmax probabilities.
- Confidence threshold: `DAMAGE_CONFIDENCE_THRESHOLD` env (default 0.75).

**Confidence Thresholds:**
- `<0.75:` Omit `damage_classification` from result (insufficient confidence).
- `≥0.75:` Include in result with type and confidence score.

**InferenceResult Schema (updated):**
```json
{
  "camera_id": "cam-01",
  "image_object_key": "capture/abc123.jpg",
  "detections": [
    { "x1": 10.5, "y1": 20.3, "x2": 150.2, "y2": 180.1, "score": 0.92, "label": "parcel" }
  ],
  "fingerprint": [...],
  "damage_classification": {
    "type": "minor",
    "confidence": 0.88
  },
  "timestamp_ms": 1704067200000,
  "schema_version": 2
}
```

**Absence:** If model unavailable or confidence < threshold, `damage_classification` field is omitted (not null).

---

## Service: edge-services — role=identity (port 8083)

### Inputs
- Kafka topic `inference_results` (consumer group: `edge-identity-consumer`).
- Optional: `POST /identify` with `{ "inference": InferenceResult, "metadata"?: object }`.

### Processing
1. Extract `fingerprint[]` from `InferenceResult`.
2. Search Qdrant collection `parcel_fingerprints` (cosine, top-1) for nearest neighbor.
3. **If match score ≥ `FINGERPRINT_MATCH_THRESHOLD`:**
   - Use existing `edge_parcel_id` from matched point payload.
   - Insert `parcel_events` row with `event_type = "identified"`.
4. **If match score < threshold or collection empty:**
   - Generate new `edge_parcel_id` (UUIDv4).
   - Upsert vector in Qdrant with `{ edge_parcel_id }` payload.
   - Insert `parcels` row.
   - Insert `parcel_events` row with `event_type = "new_identity"`.
5. Encrypt `metadata` using `ENCRYPTION_KEY` (AES-256-GCM); store in `metadata_enc`.
6. Insert `sync_outbox` row with `status = "pending"` and full parcel payload.

### Outputs
- Rows in `parcels` and `parcel_events`.
- Row in `sync_outbox`.
- `GET /health` → 200 `"ok"`.
- `POST /identify` response: `{ edge_parcel_id, match_score, qdrant_point_id }`.

### Timeouts & Retries
- Qdrant search timeout: 3 s.
- Postgres write timeout: 5 s.
- On dependency error: log, skip write, do not crash consumer loop.

### Error Handling
| Condition | Behavior |
|-----------|---------|
| Qdrant unreachable | Skip vector search; treat as new identity; attempt Postgres insert; log warning |
| Postgres unreachable | Log error; skip all writes; consumer advances offset (message not reprocessed) |
| Zero-vector fingerprint | Proceed as normal; cosine similarity will be unreliable; match_score logged |
| Missing ENCRYPTION_KEY | Log critical error; metadata_enc set to null; do not expose raw metadata |

---

## Service: edge-services — role=sync (port 8084)

### Inputs
- Postgres `sync_outbox` table rows with `status = "pending"` (poll interval: configurable, default 10 s).

### Processing
1. Fetch batch of pending rows (batch size: `SYNC_BATCH_SIZE`, default 10).
2. For each row: POST payload JSON to `CLOUD_SYNC_URL` (if configured).
3. On HTTP 200: mark row `status = "sent"`, set `sent_at = now()`.
4. On non-200 or timeout: leave row `pending`; log warning; retry on next poll.
5. If `CLOUD_SYNC_URL` not configured: mark rows `sent` locally (offline mode).

### Outputs
- Updated `sync_outbox` rows.
- `GET /sync/status` → `{ "pending": N, "sent_last_hour": N }`.
- `GET /health` → 200 `"ok"`.

### Timeouts & Retries
- Cloud POST timeout: 10 s.
- Retry is poll-based (next cycle); no immediate retry to avoid thundering herd.
- Maximum row age before alerting: 30 min (see Observability Spec).

### Error Handling
| Condition | Behavior |
|-----------|---------|
| Cloud endpoint returns 4xx | Mark row `failed` (permanent error); log; do not retry |
| Cloud endpoint returns 5xx | Leave `pending`; retry next cycle |
| Cloud endpoint timeout | Leave `pending`; retry next cycle |
| Postgres unreachable | Log error; skip cycle; retry on next poll |

---

## Service: edge-services — role=routing (port 8085)

### Inputs
- `POST /route` with `{ "edge_parcel_id": string, "metadata"?: object }`.
- `POST /route/rules` with `{ "edge_parcel_id": string, "destination": string }`.

### Processing (`/route`)
1. Query `routing_rules` for `edge_parcel_id` where `enabled = true`.
2. If rule found: return `{ destination, source: "local-rule" }`.
3. If no local rule and `ROUTING_API_URL` configured: POST to cloud API (timeout: 2 s).
   - On 200: return cloud response with `source: "cloud"`.
   - On error/timeout: fall through to default.
4. Return `{ destination: LOCAL_DEFAULT, source: "local-default" }`.

### Outputs
- `POST /route` → `{ destination: string, source: "local-rule" | "cloud" | "local-default" }`.
- `POST /route/rules` → `{ "ok": true }`.
- `GET /health` → 200 `"ok"`.

### Timeouts & Retries
- Cloud routing API timeout: 2 s (hard; fallback to local default immediately).
- DB query timeout: 1 s.

### Error Handling
| Condition | Behavior |
|-----------|---------|
| Postgres unreachable | Skip rule lookup; attempt cloud; fall back to `LOCAL_DEFAULT` |
| Cloud API unreachable | Fall back to `LOCAL_DEFAULT`; log warning |
| `LOCAL_DEFAULT` not set | Return `{ destination: "UNKNOWN", source: "local-default" }`; log warning |

---

## Service: edge-services — role=monitoring (port 8086)

### Endpoints
- `GET /health` → 200 `"ok"`.
- `GET /metrics` → Prometheus text format.
- `GET /docs` → OpenAPI docs.

### Metrics Exposed
| Metric | Type | Description |
|--------|------|-------------|
| `gpu_utilization` | Gauge | GPU utilization 0.0–1.0; 0 if no GPU |
| `edge_frames_ingested_total` | Counter | Total frames published to `frames` topic |
| `edge_inference_latency_seconds` | Histogram | ONNX inference duration |
| `edge_identity_match_score` | Histogram | Qdrant cosine match scores |
| `edge_sync_outbox_pending` | Gauge | Current pending sync_outbox rows |
| `edge_sync_sent_total` | Counter | Total sync items sent to cloud |

---

## Service: ui-dashboard (port 3000)

- Next.js application.
- Reads service URLs from `NEXT_PUBLIC_*` environment variables.
- Displays links to `/health` and `/docs` for each service.
- Provides operator controls: trigger manual sync, view routing rules.
- Static build; no backend state beyond calling edge service APIs.
- Configurable via `NEXT_PUBLIC_INFERENCE_URL`, `NEXT_PUBLIC_IDENTITY_URL`, `NEXT_PUBLIC_SYNC_URL`, `NEXT_PUBLIC_ROUTING_URL`, `NEXT_PUBLIC_MONITORING_URL`.
