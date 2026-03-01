Title: Choose Postgres for Parcel State and Events
Status: Proposed
Date: 2026-03-01
Owners: Edge Platform Team

Context:
Persistent parcel identity, event history, routing rules, and outbox workflows require relational integrity and queryability.

Decision:
Use Postgres as the primary transactional store for parcels, parcel_events, routing_rules, and sync_outbox.

Alternatives Considered:
- MySQL
- Document stores (MongoDB)

Trade-offs:
- Slightly heavier operations than a document store.
- Better integrity for cross-entity relationships and auditing.

Consequences:
- Strong consistency and relational constraints for routing and outbox.
- Requires migration management and backup strategy.

Operational Impact:
- Schema migrations, vacuuming, and monitoring required.
- Connection management and pooling must be configured for scale.

Rollback Strategy:
- Revert to previous storage backend using a parallel write and backfill window.
- Freeze schema changes and export data for migration rollback.

Future Evolution:
- Enables analytical queries and reporting using SQL.
- Supports future sharding or read replicas if needed.
