# Scope Boundaries

## In Scope
- Label-less parcel recognition using image embeddings at the edge.
- Kafka-first event-driven processing for frames and inference results.
- Local parcel identity resolution with Postgres and Qdrant.
- Local routing decisions with optional cloud fallback.
- Edge-first operation with optional cloud sync via outbox.
- Observability via metrics, logs, and traces for edge services.

## Out of Scope
- Worker tracking and privacy-masked staff localization.
- Asset tracking for pallets, cages, and yard trailers.
- Automated FIFO/LIFO enforcement and dwell time governance.
- Real-time AI task allocation and workforce scheduling.
- Truck fill rate estimation and departure optimization.
- Digital twin simulation of terminals or linehaul.
- Network-level orchestration across multiple terminals.
- Sorter parameter optimization and conveyor control.
- Advanced damage detection and mis-sort analytics beyond parcel detection.

## Deferred Scope
- Privacy-masked facility-wide analytics beyond parcel tracking.
- Network-level optimization and load balancing across hubs.
- Full operational digital twin modeling for planning.

## Explicit Non-Goals
- Real-time PII identification of individuals from camera feeds.
- Full warehouse management system replacement.
- Sub-100 ms inference latency on edge CPU-only hardware.
- Multi-tenancy for unrelated logistics operators.
