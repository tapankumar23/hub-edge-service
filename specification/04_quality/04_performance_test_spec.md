# Performance Test Specification

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** SRE + Edge Platform Engineering | **Review Cadence:** Per Release

---

## Scope

| Test Type | Purpose | Frequency |
|-----------|---------|----------|
| Baseline (dev) | Validate latency SLOs; single stream | Every release |
| Load test | Validate throughput at production concurrency | Pre-prod gate |
| Stress test | Find breaking point; validate graceful degradation | Quarterly |
| Soak test | Detect memory leaks, resource drift | Quarterly |
| Inference benchmark | Isolate ONNX latency (CPU vs GPU) | Every release |

---

## Tooling

| Tool | Purpose |
|------|---------|
| **k6** | HTTP load generation |
| **Prometheus + Grafana** | Real-time metrics during test |
| **docker stats** | CPU/memory per container |
| **psutil** | Process-level resource monitoring |
| **WireMock** | Mock cloud endpoints during tests |
| **Python harness** | Kafka consumer lag monitoring |

---

## KPIs & Production SLOs

| Metric | Dev Target | Production Target | Measurement |
|--------|-----------|-------------------|-------------|
| `POST /ingest` p50 | < 100 ms | < 100 ms | k6 |
| `POST /ingest` p95 | < 250 ms | < 250 ms | k6 |
| E2E ingest → inference_results p50 | < 3 s | < 500 ms | Prometheus histogram |
| E2E ingest → inference_results p95 | < 5 s | < 1.5 s | Prometheus histogram |
| ONNX inference p50 (CPU) | < 2 s | < 400 ms | `edge_inference_latency_seconds` |
| ONNX inference p50 (GPU) | N/A | < 100 ms | `edge_inference_latency_seconds` |
| MinIO `put_object` p95 | — | < 500 ms | Client timestamps |
| Qdrant search p95 | — | < 150 ms | Client timestamps |
| `POST /route` p95 | — | < 200 ms | k6 |
| Kafka `frames` consumer lag | < 10 msgs | < 50 msgs | Consumer group metrics |
| Error rate during load | 0% | < 0.1% | k6 `http_req_failed` |

---

## T-01 — Dev Baseline (Single Stream)

**Goal:** Confirm latency SLOs on a single-core dev machine without GPU.

```bash
k6 run --vus 1 --iterations 50 scripts/perf/k6_baseline.js
```

**k6 thresholds:**
```javascript
thresholds: {
  http_req_duration: ['p(50)<3000', 'p(95)<5000'],
  http_req_failed:   ['rate<0.01'],
}
```

**Pass criteria:** p50 E2E < 3 s; p50 inference < 2 s; 0 errors.

---

## T-02 — Production Load Test

**Goal:** Validate system under 300 req/min (5 RPS) production load.

```bash
k6 run --vus 10 --duration 5m scripts/perf/k6_load.js
```

**Monitoring during test:**
- Watch `edge_inference_latency_seconds` histogram in Grafana.
- Watch Kafka `frames` consumer lag (must stay < 50 messages).
- Watch CPU/memory per container via `docker stats`.

**Pass criteria:**
- `POST /ingest` p95 < 250 ms.
- E2E p50 < 500 ms; p95 < 1.5 s.
- Kafka consumer lag < 50 messages throughout.
- CPU (inference container) < 85%.
- 0 HTTP errors; 0 container OOM kills.

---

## T-03 — Stress Test

**Goal:** Find breaking point; validate graceful degradation and recovery.

**Ramp pattern:**
```
Stage 1:  0–1 min →   5 VUs
Stage 2:  1–3 min →  20 VUs
Stage 3:  3–5 min →  50 VUs
Stage 4:  5–7 min → 100 VUs
Stage 5:  7–8 min →   0 VUs (recovery observation)
```

**Observations to record:**
- VU count at which p95 exceeds SLO.
- VU count at which error rate exceeds 1%.
- Does Kafka consumer lag recover after load drops?
- Any OOM kills or service crashes?
- Recovery time after load removed.

**Pass criteria:**
- System does not panic at any load level (errors are HTTP 503, not crashes).
- Full recovery within 60 s after load drops.

---

## T-04 — Soak Test (24 hours)

**Goal:** Detect memory leaks, resource drift, connector stability.

```bash
k6 run --vus 3 --duration 24h scripts/perf/k6_soak.js
```

**Monitoring:**
- CPU/memory sampled every 60 s via `docker stats >> soak_resources.log`.
- Kafka consumer lag sampled every 60 s.
- Postgres table sizes checked every hour.
- Qdrant point count checked every hour.

**Pass criteria:**
- Container memory growth < 20% over 24 h.
- No service restarts during soak.
- Error rate < 0.1% throughout.
- Consumer lag remains < 100 messages.

---

## T-05 — Inference Latency Benchmark

**Goal:** Isolate ONNX inference latency from pipeline overhead (CPU vs GPU).

```bash
python3 scripts/perf/benchmark_infer.py --n 100 --url http://localhost:8082/infer
```

**Metrics:** p50, p95, p99 inference duration from 100 sequential calls.

**Pass criteria:**
- CPU: p50 < 2 s; p95 < 4 s.
- GPU (if available): p50 < 100 ms; p95 < 200 ms.
- 0 errors in 100 calls.

---

## Regression Thresholds

A regression blocks merge to `main` unless waived by SRE lead.

| Metric | Regression Threshold |
|--------|---------------------|
| E2E p50 latency | > 20% increase vs. previous release |
| Ingestion throughput at 10 VU | > 10% decrease |
| Inference p50 (CPU) | Absolute value > 2 s |
| Error rate during T-02 | > 0.1% |
| Memory growth during T-04 | > 20% over 24 h |

---

## Baseline Record

| Release | Date | E2E p50 | E2E p95 | Inference p50 CPU | Max Load | Notes |
|---------|------|---------|---------|------------------|---------|-------|
| v1.0.0 | TBD | TBD | TBD | TBD | TBD | Initial |
