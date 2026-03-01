# Runtime Assumptions

Environment
- Local development targets macOS with Docker Desktop.
- docker-compose or docker compose is available.
- CPU inference is acceptable; GPU is optional.

Core Services
- Redpanda (Kafka): localhost:9092
- Postgres: localhost:5432 (host) or host.docker.internal:5433 (container access)
- MinIO: localhost:9000 (API), localhost:9001 (console)
- Qdrant: localhost:6334 (host) → container:6333
- Redis: localhost:6379
- Prometheus: localhost:9090
- Grafana: localhost:3001
- Kafka UI: localhost:8087

Edge Services
- Camera ingestion: localhost:8081
- Inference: localhost:8082
- Identity: localhost:8083
- Sync: localhost:8084
- Routing: localhost:8085
- Monitoring: localhost:8086

Required Environment Variables
- KAFKA_BROKERS
- MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET
- YOLO_MODEL_PATH
- POSTGRES_DSN (identity, sync, routing, monitoring roles)

Model Assets
- YOLO model file expected at /opt/models/yolo.onnx in the inference container.

Assumptions
- Kafka topics frames and inference_results exist or are auto-created.
- Services expose /health and /docs where applicable.
- Outbox sync is best-effort and may retry when cloud is unavailable.