from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from app.config import settings

_client = None

async def init_vector():
    global _client
    try:
        _client = AsyncQdrantClient(url=settings.qdrant_url)
        await _client.create_collection(
            collection_name="parcel_fingerprints",
            vectors_config=VectorParams(size=settings.embed_dim, distance=Distance.COSINE)
        )
    except Exception:
        _client = None

async def upsert_vector(point_id, vector, payload):
    if _client is None:
        return
    await _client.upsert(
        collection_name="parcel_fingerprints",
        points=[PointStruct(id=point_id, vector=vector, payload=payload)]
    )

async def search_vector(vector, limit=1):
    if _client is None:
        return []
    res = await _client.search(
        collection_name="parcel_fingerprints",
        query_vector=vector,
        limit=limit
    )
    return res
