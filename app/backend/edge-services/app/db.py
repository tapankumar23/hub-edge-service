import asyncpg
from cryptography.fernet import Fernet
from app.config import settings

_pool = None
_fernet = None

async def init_db():
    global _pool, _fernet
    try:
        _pool = await asyncpg.create_pool(settings.postgres_dsn)
        async with _pool.acquire() as conn:
            pass
    except Exception:
        _pool = None
    key = settings.encryption_key.encode()
    if len(key) != 32:
        key = key.ljust(32, b"_")[:32]
    fkey = Fernet.generate_key()
    _fernet = Fernet(fkey)

async def insert_parcel(edge_parcel_id, qdrant_point_id, image_object_key, camera_id, fingerprint_dim, metadata):
    if _pool is None:
        return
    enc = _fernet.encrypt(str(metadata).encode())
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO parcels(edge_parcel_id, qdrant_point_id, image_object_key, camera_id, fingerprint_dim, metadata_enc)
               VALUES($1,$2,$3,$4,$5,$6)""",
            edge_parcel_id, qdrant_point_id, image_object_key, camera_id, fingerprint_dim, enc
        )

async def insert_event(edge_parcel_id, event_type, payload):
    if _pool is None:
        return
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO parcel_events(edge_parcel_id, event_type, payload)
               VALUES($1,$2,$3)""",
            edge_parcel_id, event_type, payload
        )

async def enqueue_sync(destination, payload):
    if _pool is None:
        return
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO sync_outbox(destination, payload, status)
               VALUES($1,$2,'pending')""",
            destination, payload
        )

async def fetch_outbox(limit=100):
    if _pool is None:
        return []
    async with _pool.acquire() as conn:
        return await conn.fetch(
            """SELECT id, destination, payload, retries
               FROM sync_outbox
               WHERE status='pending'
               ORDER BY created_at
               LIMIT $1""",
            limit
        )

async def mark_outbox_sent(item_id):
    if _pool is None:
        return
    async with _pool.acquire() as conn:
        await conn.execute(
            "UPDATE sync_outbox SET status='sent' WHERE id=$1",
            item_id
        )

async def update_routing_rules():
    return []

async def get_destination_rule(edge_parcel_id):
    if _pool is None:
        return None
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT destination FROM routing_rules WHERE rule_name=$1 AND enabled=TRUE ORDER BY created_at DESC LIMIT 1",
            edge_parcel_id
        )
        return row["destination"] if row else None

async def set_destination_rule(edge_parcel_id, destination):
    if _pool is None:
        return
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM routing_rules WHERE rule_name=$1", edge_parcel_id)
        if row:
            await conn.execute(
                "UPDATE routing_rules SET destination=$1, enabled=TRUE WHERE id=$2",
                destination, row["id"]
            )
        else:
            await conn.execute(
                "INSERT INTO routing_rules(rule_name, rule_expression, destination, enabled) VALUES($1, $2::jsonb, $3, TRUE)",
                edge_parcel_id, {}, destination
            )

async def count_outbox_pending():
    if _pool is None:
        return 0
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(*) AS c FROM sync_outbox WHERE status='pending'")
        return row['c']
