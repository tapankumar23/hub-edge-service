import base64
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import InferenceResult, DamageClassification, DamageType

# Dummy base64 1x1 image
IMAGE_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="

@pytest.fixture
def mock_s3():
    with patch("boto3.client") as mock:
        yield mock

@pytest.fixture
def mock_inference():
    with patch("app.main.run_inference") as mock:
        yield mock

def test_infer_endpoint_no_damage(mock_s3, mock_inference):
    mock_inference.return_value = ([], [], None)
    
    with TestClient(app) as client:
        payload = {"image_base64": IMAGE_B64, "camera_id": "test-cam"}
        response = client.post("/infer", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["camera_id"] == "test-cam"
        assert "damage_classification" in data
        assert data["damage_classification"] is None

def test_infer_endpoint_with_damage(mock_s3, mock_inference):
    damage = DamageClassification(type=DamageType.minor, confidence=0.95)
    mock_inference.return_value = ([], [], damage)
    
    with TestClient(app) as client:
        payload = {"image_base64": IMAGE_B64, "camera_id": "test-cam"}
        response = client.post("/infer", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["damage_classification"] is not None
        assert data["damage_classification"]["type"] == "minor"
        assert data["damage_classification"]["confidence"] == 0.95

def test_schema_damage():
    damage = DamageClassification(type="major", confidence=0.8)
    assert damage.type == DamageType.major
    assert damage.confidence == 0.8
    assert damage.type.value == "major"
