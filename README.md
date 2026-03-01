# Hub Edge Service

> Real-time, on-device computer vision and decisioning platform for parcel facilities.

**Hub Edge Service** enables label-less recognition, identity resolution via embeddings, local routing decisions, and eventual cloud sync. It is designed to improve throughput, asset utilization, and reduce manual coordination in logistics hubs.

## 🚀 Key Features

- **Camera Ingestion**: High-performance video frame ingestion from IP cameras.
- **Edge Inference**: Real-time object detection (YOLO) and vector embedding generation.
- **Identity Resolution**: Advanced parcel matching using 768-dimensional embeddings and Qdrant vector search.
- **Smart Routing**: Local routing decisions with cloud escalation capabilities.
- **Cloud Sync**: Robust synchronization of data with central cloud systems using the outbox pattern.
- **Observability**: Comprehensive monitoring with Prometheus and Grafana.
- **Operator Dashboard**: User-friendly Next.js interface for facility operators.

## 🛠️ Tech Stack

- **Languages**: Go (Ingestion), Python (Edge Services), TypeScript (Dashboard)
- **Messaging**: Redpanda (Kafka-compatible)
- **Databases**: 
  - **PostgreSQL**: Metadata and relational data
  - **Qdrant**: Vector database for identity resolution
  - **Redis**: Caching
  - **MinIO**: S3-compatible object storage
- **Observability**: Prometheus, Grafana, Kafka UI
- **Infrastructure**: Docker Compose, Helm Charts

## 📋 Prerequisites

- **Docker** & **Docker Compose**
- **Go 1.21+** (for local development)
- **Python 3.11+** (for local development)
- **Node.js 18+** (for local development)

## 🏃‍♂️ Getting Started

### 1. Start All Services

The easiest way to run the entire stack is using Docker Compose:

```bash
docker-compose up -d --build
```

This will spin up all microservices, databases, and the frontend dashboard.

### 2. Access the Services

Once the containers are running, you can access the various interfaces:

| Service | URL | Description |
|---------|-----|-------------|
| **Operator Dashboard** | [http://localhost:3000](http://localhost:3000) | Main UI for operators |
| **Grafana** | [http://localhost:3001](http://localhost:3001) | Metrics dashboards |
| **Prometheus** | [http://localhost:9090](http://localhost:9090) | Metric collection |
| **Kafka UI** | [http://localhost:8087](http://localhost:8087) | Inspect Kafka topics |
| **MinIO Console** | [http://localhost:9001](http://localhost:9001) | Object storage browser |

### 3. API Endpoints

| Service Role | Port | Description |
|--------------|------|-------------|
| `camera-ingestion` | 8081 | Image ingestion |
| `inference` | 8082 | Object detection & embedding |
| `identity` | 8083 | Vector search & ID resolution |
| `sync` | 8084 | Cloud synchronization |
| `routing` | 8085 | Routing decisions |
| `monitoring` | 8086 | System health & metrics |

## 📂 Project Structure

```
hub-edge-service/
├── services/               # Backend microservices
│   ├── camera-ingestion/   # Go service for camera handling
│   └── edge-services/      # Python services (Inference, Identity, Sync, Routing)
├── ui-dashboard/           # Next.js frontend application
├── specification/          # Detailed product and architecture documentation
├── helm/                   # Helm charts for Kubernetes deployment
├── infra/                  # Infrastructure config (Grafana, Prometheus)
├── models/                 # ML models (e.g., YOLO ONNX)
├── scripts/                # Helper scripts for testing and maintenance
└── docker-compose.yml      # Local development orchestration
```

## 📚 Documentation

Detailed documentation is available in the `specification/` directory:

- [Product Vision](specification/01_product/01_product_vision.md)
- [System Architecture](specification/02_architecture/01_system_architecture.md)
- [API Contracts](specification/02_architecture/07_api_contracts.yaml)
- [Functional Flow](specification/01_product/06_functional_flow.md)

## 🧪 Testing

Run the end-to-end test script:

```bash
./scripts/run_p0_e2e.sh
```

## 📜 License

Internal Use Only.
