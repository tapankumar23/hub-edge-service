# Sample Payloads & Fixtures

Camera Ingestion
- POST /ingest

```json
{
  "camera_id": "cam-01",
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
}
```

FrameEvent (Kafka: frames)

```json
{
  "camera_id": "cam-01",
  "timestamp": 1700000000000,
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
}
```

Inference API
- POST /infer

```json
{
  "camera_id": "cam-01",
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
}
```

InferenceResult (Kafka: inference_results)

```json
{
  "camera_id": "cam-01",
  "timestamp": 1700000000100,
  "detections": [
    { "x1": 12.3, "y1": 45.6, "x2": 210.4, "y2": 320.2, "score": 0.91, "label": "parcel" }
  ],
  "fingerprint": [0.01, 0.02, 0.03, 0.04],
  "image_object_key": "capture/2b9c4a7d-2e5c-45c1-a1b7-1a9a14a0f9b1.jpg"
}
```

Identity API
- POST /identify

```json
{
  "inference": {
    "camera_id": "cam-01",
    "timestamp": 1700000000100,
    "detections": [
      { "x1": 12.3, "y1": 45.6, "x2": 210.4, "y2": 320.2, "score": 0.91, "label": "parcel" }
    ],
    "fingerprint": [0.01, 0.02, 0.03, 0.04],
    "image_object_key": "capture/2b9c4a7d-2e5c-45c1-a1b7-1a9a14a0f9b1.jpg"
  },
  "metadata": {}
}
```

Route API
- POST /route

```json
{
  "edge_parcel_id": "edge-6b2d9f2a-1234-4ef2-9c2b-aaaabbbbcccc",
  "metadata": {}
}
```

RouteResponse

```json
{
  "destination": "LOCAL_DEFAULT",
  "source": "local"
}
```