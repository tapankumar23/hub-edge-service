# Traceability Matrix

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** Edge Platform PM + QA | **Review Cadence:** Per Release

---

## Revision Log

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0.0 | 2026-03-01 | Edge Platform Team | Initial production version |

---

## Functional Requirements → Tests

| Req ID | Requirement | User Story | Functional Spec | Acceptance Test | Integration Test | NFR |
|--------|------------|-----------|-----------------|----------------|-----------------|-----|
| FR-01 | Ingest image → Kafka `frames` | US-ENG-01, US-OP-02 | Functional: camera-ingestion | Step 2–3 | IT-01 | OR-01 |
| FR-02 | YOLO detect + embed → `inference_results` | US-ENG-02, US-ENG-04 | Functional: inference | Step 4 | IT-02 | — |
| FR-03 | Store image in MinIO | US-ENG-03 | Functional: inference (MinIO) | Step 5 | IT-02 | — |
| FR-04 | Qdrant nearest-neighbor identity | US-ML-01 | Functional: identity | Step 6 (partial) | IT-03 | — |
| FR-05 | Persist `parcels` + `parcel_events` | US-ML-01 | Functional: identity (Postgres) | Step 6 | IT-03 | — |
| FR-06 | Drain `sync_outbox` to cloud | US-ADM-01 | Functional: sync | Step 7 | IT-04 | — |
| FR-07 | Local routing decision + fallback | US-ADM-03 | Functional: routing | Step 8 | IT-05, IT-06 | — |
| FR-08 | `/health` on all services | US-OP-01 | Functional: all services | Step 1 | IT-07 | OR-01 |
| FR-09 | Operator dashboard | US-OP-03 | Functional: dashboard | — | — | — |
| FR-10 | `/route/rules` per-parcel rule | US-ADM-02 | Functional: routing | — | IT-05 | — |
| FR-11 | Prometheus `/metrics` | US-SRE-01 | Functional: monitoring | — | IT-07 | — |
| FR-12 | `metadata_enc` encryption | — | Functional: identity | — | — | SC-03 |
| FR-13 | Camera capture loop | — | Functional: camera-ingestion | — | — | OR-09 |
| FR-14 | Cloud routing override | US-ADM-03 | Functional: routing (cloud) | — | IT-06 | — |
| FR-15 | Classify parcel damage (none/minor/major) | — | Functional: inference (damage classification) | Step 5+ | IT-02 | — |

---

## Non-Functional Requirements → Tests

| NFR | Requirement | Performance Test | Acceptance/Integration | Chaos Test |
|-----|------------|-----------------|----------------------|-----------|
| Availability ≥ 99.9% | All services | T-04 (soak) | N-06 (dependency outage) | Kill Postgres scenario |
| E2E p50 < 500 ms (prod) | Pipeline latency | T-02 load test | Step 4 timing | — |
| ONNX p50 < 400 ms (prod) | Inference latency | T-05 benchmark | — | — |
| RTO < 15 min | Recovery time | T-04 recovery obs. | N-06 recovery | Kill Kafka scenario |
| Routing always returns destination | Routing reliability | T-02 | N-04 (unknown parcel) | Kill Postgres scenario |
| No secrets in logs | Security | CI log scan | — | — |
| Metadata encrypted at rest | Security | — | — | ENCRYPTION_KEY missing |
| Kafka at-least-once | Reliability | T-03 stress | — | Kill Redpanda mid-test |
| Identity idempotent | Reliability | — | IT-03 idempotency | — |
| Structured JSON logs | Operability | — | US-SRE-02 | — |
| Consumer lag < 50 msgs | Throughput | T-02, T-04 | — | — |

---

## Security Requirements → Tests

| Security Req | Spec Ref | Test |
|-------------|---------|------|
| No secrets in logs | SC-01 | CI log scanning job |
| Secrets via env only | SC-02 | Code review + CI secret scan |
| AES-256-GCM metadata encryption | SC-03 | Integration: identity service unit test |
| HTTPS for cloud sync in production | SC-04 | Startup config validation test |
| Privacy masking on camera feeds | SC-05 | Code review |
| No PII in Kafka payloads | SC-06 | Schema review + integration test |
| Key rotation support | SC-07 | IT-08 (key rotation integration test); runbook (doc 02) |
| Bearer token auth in production | SC-08 | API contract + reverse proxy config |

---

## User Story Coverage

| User Story | FR Coverage | Test Coverage | Status |
|-----------|------------|--------------|--------|
| US-OP-01 — Health verification | FR-08 | Acceptance Step 1; US-SRE-01 | Covered |
| US-OP-02 — E2E pipeline validation | FR-01–FR-07 | Acceptance Steps 1–8 | Covered |
| US-OP-03 — Operator dashboard | FR-09 | Manual (no automated test) | Partial |
| US-ENG-01 — Ingestion validation | FR-01 | IT-01; Acceptance Step 2–3 | Covered |
| US-ENG-02 — ML pipeline output | FR-02 | IT-02; Acceptance Step 4 | Covered |
| US-ENG-03 — MinIO persistence | FR-03 | IT-02; Acceptance Step 5 | Covered |
| US-ENG-04 — Direct /infer | FR-02 | IT-02 | Covered |
| US-ML-01 — Vector linkage | FR-04, FR-05 | IT-03 | Covered |
| US-ML-02 — Threshold config | FR-04 | Manual; env var documented | Partial |
| US-ADM-01 — Sync outbox drain | FR-06 | IT-04; Acceptance Step 7 | Covered |
| US-ADM-02 — Routing rules | FR-10 | IT-05 | Covered |
| US-ADM-03 — Cloud routing | FR-14 | IT-06 | Covered |
| US-SRE-01 — Prometheus metrics | FR-11 | IT-07 | Covered |
| US-SRE-02 — Structured logs | OR-08 | CI log format validation | Partial |

---

## Coverage Gaps & Remediation

| Gap | Risk | Remediation |
|-----|------|------------|
| FR-09 dashboard: no automated tests | Low | Add Playwright smoke test in next sprint |
| US-ML-02 threshold: no automated test | Medium | Add unit test parameterizing FINGERPRINT_MATCH_THRESHOLD |
| US-SRE-02 log format: no automated validation | Medium | Add CI step parsing log output as JSON |
| SC-04 HTTPS enforcement: startup test | High | Add config validation unit test asserting URL scheme in prod mode |
| Chaos tests: not in CI pipeline | Medium | Schedule quarterly chaos day; add chaos test job to nightly CI |
