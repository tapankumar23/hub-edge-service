# Product Vision

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** Product — Edge Platform | **Review Cadence:** Quarterly

---

## Executive Summary

Edge Hub brings real-time, on-device computer vision and decisioning to parcel facilities. It enables label-less recognition, identity via embeddings, local routing decisions, and eventual cloud sync. Outcomes include improved throughput, better asset utilization, and reduced manual coordination.

---

## Stakeholders

| Role | Team | Interest |
|------|------|---------|
| Executive Sponsor | VP Logistics Engineering | ROI, delivery SLA improvement |
| Product Owner | Edge Platform PM | Feature scope, roadmap, KPI accountability |
| Engineering Lead | Edge Services Team | Architecture, delivery, operational health |
| Facility Operators | Hub Operations | Reliable runtime; actionable dashboard |
| Data / ML Engineers | ML Platform | Embedding quality, model iteration |
| Fleet Admins | Network Operations | Cloud sync accuracy, routing correctness |
| Security | InfoSec | Credential management, data encryption |
| Compliance | Legal / Privacy | GDPR/privacy masking for camera feeds |
| SRE | Platform SRE | Availability, incident response, on-call |

---

## Key Problem Statements

- **Real-time visibility gaps:** managers cannot see where staff and assets are; manual monitoring wastes time.
- **Inefficient storage and flow:** FIFO/LIFO violations and untracked dwell time increase mis-sort rates.
- **Under-optimized staffing:** workers wait for instructions; static zone staffing fails during demand spikes.
- **Low equipment utilization:** trucks depart under-filled; chutes get blocked without detection.
- **Push-based operations:** work pushed without downstream capacity awareness creates congestion.
- **Static capacity planning:** centers operate independently; sort plans are largely static.
- **Label dependency:** accuracy tied to readable labels; damaged or missing labels cause manual fallback.
- **Labor shortages:** need for resilient automation that reduces dependence on manual scanning.

---

## Solution Pillars

1. **CV-based smart terminals** — cameras monitor worker positions (privacy-masked), storage areas, FIFO/LIFO compliance, chute blockages, and yard assets.
2. **Real-time AI task allocation** — dynamic instructions shift staffing from fixed zones to demand-based teams.
3. **Truck fill rate monitoring** — continuously estimate fill rates; alert before departure thresholds.
4. **Pull-based flow optimization** — connect arrival, sorting, and departure signals to prevent congestion.
5. **Digital twins** — simulate terminal and linehaul to evaluate operational changes before deployment.
6. **Label-less vision sorting** — identify parcels by image embeddings; detect damage and mis-sorts.
7. **Network-level orchestration** — rebalance volumes across centers based on real-time capacity and demand.
8. **Sorter parameter optimization** — dynamically adjust conveyor speed, circulation, and sort plans.

---

## Goals

- Automate parcel identification without printed labels using embeddings and nearest-neighbor search.
- Keep core decisions and storage at the edge; sync to cloud opportunistically with conflict resolution.
- Provide a modular, Kafka-first architecture composing ingestion, inference, identity, sync, routing, and monitoring.
- Be operable locally via Docker Compose with clear health checks, end-to-end tests, and runbooks.
- Achieve production-grade observability: structured logs, distributed traces, Prometheus metrics, and alerting.

---

## Success KPIs

| KPI | Baseline | Target (6 months) | Measurement |
|-----|---------|-------------------|-------------|
| Parcel mis-sort rate | ~2.5% | < 0.8% | Cloud registry vs. physical audit |
| Label-less identification accuracy | 0% | ≥ 95% top-1 | Offline eval dataset |
| E2E pipeline latency p50 | N/A | < 500 ms | Prometheus histogram |
| Edge service availability | N/A | ≥ 99.9% | Uptime monitoring |
| Cloud sync lag p95 | N/A | < 5 min | sent_at − created_at |
| Operator dashboard load time | N/A | < 2 s | Lighthouse / RUM |
| Incident MTTR | N/A | < 30 min | PagerDuty reports |

---

## Value Proposition

- **Operational:** Shorter cycle times and fewer misroutes through on-device intelligence.
- **Resilience:** Edge operation during connectivity loss with eventual cloud synchronization.
- **Insight:** Clear visibility via Prometheus/Grafana and operator dashboard.
- **Compliance:** Privacy-masked camera feeds; metadata encrypted at rest.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| GPU unavailable at edge sites | High | Medium | CPU fallback via ONNX Runtime; accept higher latency |
| Qdrant vector drift over time | Medium | High | Scheduled re-embedding jobs; version payloads |
| Cloud connectivity loss | High | Medium | Outbox pattern; local routing fallback |
| ENCRYPTION_KEY rotation | Low | High | Key versioning in metadata_enc header; rotation runbook |
| Camera feed privacy violation | Low | Critical | Privacy masking at ingestion; no PII in Kafka topics |
| YOLO model version mismatch | Medium | Medium | Pin model version in container image; migration runbook |

---

## Timeline / Milestones

| Milestone | Target | Criteria |
|-----------|--------|---------|
| M1 — Core pipeline operational | Q1 2026 | P0 E2E test passes on dev hardware |
| M2 — Production deployment (1 pilot facility) | Q2 2026 | SLOs met; Grafana dashboards live; on-call established |
| M3 — Label-less ID accuracy ≥ 95% | Q3 2026 | Offline eval + shadow mode validation |
| M4 — Multi-facility rollout | Q4 2026 | 5 facilities; centralized cloud registry active |

---

## Non-Goals

- Real-time PII identification of individuals from camera feeds.
- Full warehouse management system (WMS) replacement.
- Sub-100 ms inference latency in the initial release (edge CPU constraint).
- Multi-tenancy for unrelated logistics operators.

---

## Navigation

See 00_index.md for the full documentation index.
