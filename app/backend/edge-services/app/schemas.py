from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class DamageType(str, Enum):
    none = "none"
    minor = "minor"
    major = "major"

class DamageClassification(BaseModel):
    type: DamageType
    confidence: float

class FrameIn(BaseModel):
    image_base64: Optional[str] = None
    object_key: Optional[str] = None
    camera_id: Optional[str] = None

class Detection(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    score: float
    label: str

class InferenceResult(BaseModel):
    camera_id: str
    timestamp: int
    detections: List[Detection]
    fingerprint: List[float]
    image_object_key: str
    damage_classification: Optional[DamageClassification] = None

class IdentifyRequest(BaseModel):
    inference: InferenceResult
    metadata: dict

class IdentifyResponse(BaseModel):
    edge_parcel_id: str
    match_score: float
    qdrant_point_id: str

class RouteRequest(BaseModel):
    edge_parcel_id: str
    metadata: dict

class RouteResponse(BaseModel):
    destination: str
    source: str

class RouteRuleSet(BaseModel):
    edge_parcel_id: str
    destination: str
