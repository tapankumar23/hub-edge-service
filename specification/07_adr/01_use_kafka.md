Title: Adopt Kafka (Redpanda) for Event Streaming
Status: Proposed
Date: 2026-03-01
Owners: Edge Platform Team

Context:
The system requires decoupled ingestion, inference, and identity workflows with durable messaging and replayability across edge services.

Decision:
Use Redpanda as the Kafka-compatible event streaming platform and standardize on topics frames and inference_results.

Alternatives Considered:
- Direct HTTP calls between services
- Redis Streams

Trade-offs:
- Higher operational overhead than synchronous HTTP.
- Better resilience, scalability, and async processing guarantees.

Consequences:
- Enables loose coupling and replayable processing across services.
- Adds operational complexity around broker lifecycle and offsets.

Operational Impact:
- Requires broker monitoring, topic management, and retention policy configuration.
- Adds dependency on rpk tooling for topic inspection.

Rollback Strategy:
- Revert producers and consumers to synchronous HTTP workflows for critical paths.
- Pause topic creation and archive event schemas.

Future Evolution:
- Enable additional async services without changing producers.
- Support backfill/replay for reprocessing and model upgrades.
