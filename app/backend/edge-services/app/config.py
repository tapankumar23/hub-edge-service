from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    service_role: str = "inference"
    kafka_brokers: str = "redpanda:9092"
    postgres_dsn: str = "postgresql://edge:edgepass@postgres:5432/edgehub"
    qdrant_url: str = "http://qdrant:6333"
    fingerprint_match_threshold: float = 0.85
    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "minio"
    minio_secret_key: str = "minio123"
    minio_bucket: str = "parcels"
    cloud_sync_url: str = ""
    device_id: str = "hub-001"
    signing_secret: str = ""
    routing_api_url: str = ""
    routing_timeout_ms: int = 500
    encryption_key: str = "change_me_32_bytes_key__________"
    yolo_model_path: str = "/opt/models/yolo.onnx"
    yolo_input_size: int = 640
    yolo_conf_threshold: float = 0.25
    yolo_iou_threshold: float = 0.45
    yolo_labels: str = "parcel"
    embed_model_path: str = ""
    embed_input_size: int = 224
    embed_dim: int = 768

settings = Settings()
