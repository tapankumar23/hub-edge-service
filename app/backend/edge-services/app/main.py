import base64
import json
import time
import uuid
import asyncio
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from app.config import settings
from app.schemas import FrameIn, InferenceResult, IdentifyRequest, IdentifyResponse, RouteRequest, RouteResponse, RouteRuleSet
from app.model import run_inference
from app.db import init_db, insert_parcel, insert_event, enqueue_sync, fetch_outbox, mark_outbox_sent, get_destination_rule, set_destination_rule
try:
    from app.vector import init_vector, upsert_vector, search_vector
except Exception:
    async def init_vector():
        return
    async def upsert_vector(point_id, vector, payload):
        return
    async def search_vector(vector, limit=1):
        return []
import httpx
import boto3
from botocore.exceptions import ClientError
from prometheus_client import generate_latest, Gauge, Counter, Histogram
import pynvml

app = FastAPI()

# Metrics
INFERENCE_REQUESTS = Counter("inference_requests_total", "Total inference requests")
INFERENCE_LATENCY = Histogram("inference_latency_seconds", "Inference latency")
IDENTITY_REQUESTS = Counter("identity_requests_total", "Total identity resolution requests")
ROUTING_REQUESTS = Counter("routing_requests_total", "Total routing requests")
SYNC_QUEUE_DEPTH = Gauge("sync_queue_depth", "Number of pending sync operations")
GPU_UTIL = Gauge("gpu_utilization", "GPU utilization percent")

producer = None
s3 = None

@app.on_event("startup")
async def startup():
    global producer, s3
    if settings.service_role in ["inference", "identity", "sync", "routing", "monitoring"]:
        try:
            await init_db()
        except Exception:
            pass
    if settings.service_role in ["identity"]:
        try:
            await init_vector()
        except Exception:
            pass
    if settings.service_role in ["inference"]:
        try:
            producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_brokers)
            await producer.start()
        except Exception:
            producer = None
    if settings.service_role == "monitoring":
        try:
            pynvml.nvmlInit()
        except Exception:
            pass
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key
    )
    try:
        s3.head_bucket(Bucket=settings.minio_bucket)
    except ClientError:
        try:
            s3.create_bucket(Bucket=settings.minio_bucket)
        except ClientError:
            pass
    if settings.service_role == "inference":
        asyncio.create_task(consume_frames())
    if settings.service_role == "identity":
        asyncio.create_task(consume_inference_results())
    if settings.service_role == "sync":
        asyncio.create_task(sync_loop())

@app.on_event("shutdown")
async def shutdown():
    if producer:
        await producer.stop()

@app.get("/health", response_class=PlainTextResponse)
async def health():
    return "ok"

@app.get("/sync/status")
async def sync_status():
    from app.db import count_outbox_pending
    pending = await count_outbox_pending()
    SYNC_QUEUE_DEPTH.set(pending)
    return {"pending": pending}

@app.post("/infer", response_model=InferenceResult)
async def infer(frame: FrameIn):
    INFERENCE_REQUESTS.inc()
    with INFERENCE_LATENCY.time():
        image_bytes = b""
        if frame.image_base64:
            image_bytes = base64.b64decode(frame.image_base64)
        elif frame.object_key:
            obj = s3.get_object(Bucket=settings.minio_bucket, Key=frame.object_key)
            image_bytes = obj["Body"].read()
        detections, fingerprint, damage = run_inference(image_bytes)
        object_key = frame.object_key or f"capture/{uuid.uuid4()}.jpg"
        if not frame.object_key and image_bytes:
            s3.put_object(Bucket=settings.minio_bucket, Key=object_key, Body=image_bytes)
        return InferenceResult(
            camera_id=frame.camera_id or "unknown",
            timestamp=int(time.time() * 1000),
            detections=detections,
            fingerprint=fingerprint,
            image_object_key=object_key,
            damage_classification=damage
        )

@app.post("/identify", response_model=IdentifyResponse)
async def identify(req: IdentifyRequest):
    IDENTITY_REQUESTS.inc()
    res = await search_vector(req.inference.fingerprint, limit=1)
    match_score = 0.0
    qdrant_point_id = str(uuid.uuid4())
    edge_parcel_id = "edge-" + str(uuid.uuid4())
    if res:
        match_score = res[0].score
        qdrant_point_id = str(res[0].id)
        if match_score >= settings.fingerprint_match_threshold:
            edge_parcel_id = res[0].payload["edge_parcel_id"]
    if match_score < settings.fingerprint_match_threshold:
        await upsert_vector(qdrant_point_id, req.inference.fingerprint, {"edge_parcel_id": edge_parcel_id})
        await insert_parcel(edge_parcel_id, qdrant_point_id, req.inference.image_object_key, req.inference.camera_id, len(req.inference.fingerprint), req.metadata)
    await insert_event(edge_parcel_id, "identified", {"score": match_score})
    await enqueue_sync("cloud_registry", {"edge_parcel_id": edge_parcel_id})
    try:
        dest = await get_destination_rule(edge_parcel_id)
        if not dest:
            await set_destination_rule(edge_parcel_id, "LOCAL_DEFAULT")
    except Exception:
        pass
    return IdentifyResponse(edge_parcel_id=edge_parcel_id, match_score=match_score, qdrant_point_id=qdrant_point_id)

@app.post("/route", response_model=RouteResponse)
async def route(req: RouteRequest):
    ROUTING_REQUESTS.inc()
    try:
        dest = await get_destination_rule(req.edge_parcel_id)
        if dest:
            return RouteResponse(destination=dest, source="local-rule")
    except Exception:
        pass
    if settings.routing_api_url:
        try:
            async with httpx.AsyncClient(timeout=settings.routing_timeout_ms / 1000) as client:
                r = await client.post(settings.routing_api_url, json=req.model_dump())
                if r.status_code == 200:
                    data = r.json()
                    return RouteResponse(destination=data["destination"], source="cloud")
        except Exception:
            pass
    return RouteResponse(destination="LOCAL_DEFAULT", source="local")

@app.get("/metrics")
async def metrics():
    if settings.service_role == "monitoring":
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            GPU_UTIL.set(util.gpu)
        except Exception:
            GPU_UTIL.set(0)
    
    if settings.service_role == "sync":
        try:
            from app.db import count_outbox_pending
            pending = await count_outbox_pending()
            SYNC_QUEUE_DEPTH.set(pending)
        except Exception:
            pass
            
    return PlainTextResponse(generate_latest().decode())

@app.post("/route/rules")
async def set_route_rule(rule: RouteRuleSet):
    await set_destination_rule(rule.edge_parcel_id, rule.destination)
    return {"ok": True}

async def consume_frames():
    consumer = AIOKafkaConsumer(
        "frames",
        bootstrap_servers=settings.kafka_brokers,
        value_deserializer=lambda v: json.loads(v.decode())
    )
    await consumer.start()
    try:
        async for msg in consumer:
            payload = msg.value
            frame = FrameIn(image_base64=payload["image_base64"], camera_id=payload["camera_id"])
            res = await infer(frame)
            await producer.send_and_wait("inference_results", json.dumps(res.model_dump()).encode())
    finally:
        await consumer.stop()

async def consume_inference_results():
    consumer = AIOKafkaConsumer(
        "inference_results",
        bootstrap_servers=settings.kafka_brokers,
        value_deserializer=lambda v: json.loads(v.decode())
    )
    await consumer.start()
    try:
        async for msg in consumer:
            payload = msg.value
            req = IdentifyRequest(inference=InferenceResult(**payload), metadata={})
            await identify(req)
    finally:
        await consumer.stop()

async def sync_loop():
    while True:
        items = await fetch_outbox(limit=50)
        if not items:
            await asyncio.sleep(5)
            continue
        for item in items:
            try:
                if settings.cloud_sync_url:
                    async with httpx.AsyncClient(timeout=settings.routing_timeout_ms / 1000) as client:
                        r = await client.post(settings.cloud_sync_url, json=item["payload"]) 
                        if r.status_code == 200:
                            await mark_outbox_sent(item["id"])
                else:
                    await mark_outbox_sent(item["id"])
            except Exception:
                pass
        await asyncio.sleep(1)
