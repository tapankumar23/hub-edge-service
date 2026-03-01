# Domain Glossary

## Core Concepts
- Edge Hub: The on-site system that ingests images, runs inference, resolves identity, and routes parcels.
- Parcel: A physical shipment item tracked through identity and routing.
- Label-less recognition: Identifying parcels by image similarity rather than barcode labels.
- FrameEvent: A Kafka message carrying a captured image and metadata.
- InferenceResult: A structured result containing detections, fingerprint, and image object key.
- Fingerprint: Vector embedding derived from detected parcel regions.
- Identity: The resolved edge_parcel_id representing a parcel instance.
- Outbox: A persistent queue of items pending sync to cloud systems.
- Routing rule: A local mapping from edge_parcel_id to destination.

## Entity Dictionary
- edge_parcel_id: Unique identifier for a parcel identity at the edge.
- qdrant_point_id: ID of the vector record stored in Qdrant.
- image_object_key: MinIO object key where an image is stored.
- camera_id: Identifier of the camera source.
- fingerprint_dim: Dimensionality of the embedding vector.
- metadata_enc: Encrypted metadata blob stored with the parcel.

## Service Roles
- Inference: Consumes frames, runs detection/embedding, publishes inference_results.
- Identity: Consumes inference_results, resolves identity, writes Postgres/Qdrant, enqueues outbox.
- Sync: Drains outbox and pushes to cloud.
- Routing: Returns destination using local rules or cloud fallback.
- Monitoring: Exposes metrics for Prometheus.

## Topics
- frames: FrameEvent messages produced by camera-ingestion.
- inference_results: InferenceResult messages produced by inference role.
