#!/usr/bin/env bash

# P0 End-to-end journey: ingest → frames → inference → MinIO + inference_results
#                        → identity → Postgres + Qdrant → outbox → sync → routing

IMAGE_B64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
KAFKA_CONTAINER="redpanda"
PG_DSN_DEFAULT="postgresql://postgres:postgres@localhost:5433/edgehub"
PG_DSN="${PG_DSN:-$PG_DSN_DEFAULT}"

fail() { echo "[FAIL] $1"; exit 1; }
ok()   { echo "[OK]   $1"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

echo "=== P0 Business Journey (End-to-End) ==="

echo "Checking required tools..."
require_cmd curl
if command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  DC="docker compose"
else
  fail "Missing required command: docker-compose or docker compose"
fi
require_cmd psql
ok "Required tools present"

echo
echo "Step 0: Basic health checks"
for url in \
  "http://localhost:8081/health" \
  "http://localhost:8082/health" \
  "http://localhost:8083/health" \
  "http://localhost:8084/health" \
  "http://localhost:8085/health" \
  "http://localhost:8086/health"
do
  code=$(curl -s -o /dev/null -m 5 -w "%{http_code}" "$url" || true)
  [ "$code" -ge 200 ] && [ "$code" -lt 400 ] || fail "Health check failed for $url (code=$code)"
done
ok "Core services healthy"

echo
echo "Step 1: Ingest parcel image via camera ingestion"
payload=$(printf '{"camera_id":"p0-test","image_base64":"%s"}' "$IMAGE_B64")
code=$(curl -s -o /tmp/p0_ingest_body.txt -w "%{http_code}" \
  -X POST http://localhost:8081/ingest \
  -H "Content-Type: application/json" \
  -d "$payload" || true)
[ "$code" = "202" ] || fail "Expected 202 from /ingest, got $code"
ok "Image ingested (202 Accepted)"

echo
echo "Step 2: Verify frames message in Kafka"
found=0
for i in 1 2 3 4 5; do
  FRAMES_MSG=$($DC exec -T "$KAFKA_CONTAINER" rpk topic consume frames --offset end -n 1 -f '%v\\n' 2>/dev/null || true)
  echo "$FRAMES_MSG" | grep -q '"image_base64"' && { found=1; break; }
  sleep_seconds=$((2**(i-1)))
  sleep "$sleep_seconds"
done
[ "$found" -eq 1 ] || fail "frames topic does not contain expected JSON payload"
ok "frames topic has image payload"

echo
echo "Step 3: Verify inference_results in Kafka"
found=0
for i in 1 2 3 4 5; do
  INF_MSG=$($DC exec -T "$KAFKA_CONTAINER" rpk topic consume inference_results --offset end -n 1 -f '%v\\n' 2>/dev/null || true)
  echo "$INF_MSG" | grep -q '"fingerprint"' && { found=1; break; }
  sleep_seconds=$((2**(i-1)))
  sleep "$sleep_seconds"
done
[ "$found" -eq 1 ] || fail "inference_results topic does not contain fingerprint field"
ok "inference_results topic has inference payload"

echo
echo "Step 4: Check Postgres for parcels, events, and outbox"
export PGPASSWORD="${PGPASSWORD:-postgres}"

PARCELS_COUNT=$(psql "$PG_DSN" -t -A -c "SELECT count(*) FROM parcels;" 2>/dev/null || echo "0")
echo "$PARCELS_COUNT" | grep -Eq '^[0-9]+$' || fail "Invalid parcels count: $PARCELS_COUNT"
[ "$PARCELS_COUNT" -gt 0 ] || fail "No parcels stored in DB"
ok "Parcels table has rows ($PARCELS_COUNT)"

EVENTS_COUNT=$(psql "$PG_DSN" -t -A -c "SELECT count(*) FROM parcel_events;" 2>/dev/null || echo "0")
echo "$EVENTS_COUNT" | grep -Eq '^[0-9]+$' || fail "Invalid parcel_events count: $EVENTS_COUNT"
[ "$EVENTS_COUNT" -gt 0 ] || fail "No parcel_events stored in DB"
ok "parcel_events table has rows ($EVENTS_COUNT)"

OUTBOX_PENDING=$(psql "$PG_DSN" -t -A -c "SELECT count(*) FROM sync_outbox WHERE status='pending';" 2>/dev/null || echo "0")
echo "$OUTBOX_PENDING" | grep -Eq '^[0-9]+$' || fail "Invalid sync_outbox pending count: $OUTBOX_PENDING"
[ "$OUTBOX_PENDING" -ge 0 ] || fail "Unexpected negative pending count"
ok "sync_outbox pending count = $OUTBOX_PENDING"

echo
echo "Step 5: Sync status via /sync/status"
code=$(curl -s -o /tmp/p0_sync_status.txt -w "%{http_code}" http://localhost:8084/sync/status || true)
[ "$code" = "200" ] || fail "Expected 200 from /sync/status, got $code"
ok "Sync status reachable (200)"
echo "Sync status body:"
cat /tmp/p0_sync_status.txt
echo

echo
echo "Step 6: Routing decision via /route"
ROUTE_PAYLOAD='{"edge_parcel_id":"p0-test-edge","metadata":{}}'
code=$(curl -s -o /tmp/p0_route_resp.txt -w "%{http_code}" \
  -X POST http://localhost:8085/route \
  -H "Content-Type: application/json" \
  -d "$ROUTE_PAYLOAD" || true)
[ "$code" = "200" ] || fail "Expected 200 from /route, got $code"
ok "Route endpoint reachable (200)"
echo "Route response:"
cat /tmp/p0_route_resp.txt
echo

echo "=== P0 Business Journey completed successfully ==="