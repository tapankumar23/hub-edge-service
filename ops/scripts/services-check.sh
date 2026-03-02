#!/usr/bin/env bash
set -o pipefail

ok()   { printf "[OK]    %s %s (%s)\n"   "$1" "$2" "$3"; }
fail() { printf "[FAIL]  %s %s (%s)\n"   "$1" "$2" "$3"; }
RETRIES="${CHECK_RETRIES:-5}"
BACKOFF_BASE="${CHECK_BACKOFF_BASE:-1}"

check_tcp() {
  local name="$1" host="$2" port="$3"
  if command -v nc >/dev/null 2>&1; then
    if nc -z "$host" "$port" >/dev/null 2>&1; then
      ok "$name" "$host:$port" "open"
    else
      fail "$name" "$host:$port" "closed"
    fi
  else
    (exec 3<>/dev/tcp/$host/$port) >/dev/null 2>&1 && ok "$name" "$host:$port" "open" || fail "$name" "$host:$port" "closed"
  fi
}

check_http() {
  local name="$1" url="$2"
  local attempt code
  for attempt in $(seq 1 "$RETRIES"); do
    code=$(curl -s -o /dev/null -m 5 -w "%{http_code}" "$url" || true)
    if [[ "$code" =~ ^[0-9]+$ ]] && [[ "$code" -ge 200 && "$code" -lt 400 ]]; then
      ok "$name" "$url" "$code"
      return
    fi
    sleep "$(( BACKOFF_BASE * (2 ** (attempt - 1)) ))"
  done
  fail "$name" "$url" "${code:-no-response}"
}

detect_qdrant_port() {
  for p in 6334 6333; do
    curl -s -o /dev/null -m 2 "http://localhost:$p" && echo "$p" && return
  done
  echo ""
}

echo "=== HTTP checks ==="
check_http "Dashboard"   "http://localhost:3000"
check_http "Kafka UI"    "http://localhost:8087"
check_http "Grafana"     "http://localhost:3001"
check_http "Prometheus Ready"  "http://localhost:9090/-/ready"
check_http "MinIO API"   "http://localhost:9000/minio/health/ready"
check_http "MinIO Console" "http://localhost:9001"

QPORT="$(detect_qdrant_port)"
if [[ -n "$QPORT" ]]; then
  check_http "Qdrant Root"     "http://localhost:${QPORT}/"
  check_http "Qdrant Dashboard" "http://localhost:${QPORT}/dashboard"
else
  fail "Qdrant" "http://localhost:{6333|6334}" "not-detected"
fi

check_http "Inference /health"  "http://localhost:8082/health"
check_http "Inference /docs"    "http://localhost:8082/docs"
check_http "Identity /health"   "http://localhost:8083/health"
check_http "Identity /docs"     "http://localhost:8083/docs"
check_http "Sync /health"       "http://localhost:8084/health"
check_http "Sync /docs"         "http://localhost:8084/docs"
check_http "Routing /health"    "http://localhost:8085/health"
check_http "Routing /docs"      "http://localhost:8085/docs"
check_http "Monitoring /health" "http://localhost:8086/health"
check_http "Monitoring /docs"   "http://localhost:8086/docs"
check_http "Camera Ingestion"   "http://localhost:8081/health"

echo "=== TCP checks ==="
check_tcp "Kafka" "localhost" 9092
check_tcp "Redis" "localhost" 6379

echo
echo "=== Container status ==="
if command -v docker-compose >/dev/null 2>&1; then
  docker-compose ps
elif command -v docker >/dev/null 2>&1; then
  docker compose ps
else
  echo "docker-compose not found"
fi

echo
echo "=== Database checks ==="
PG_DSN="${PG_DSN:-postgresql://postgres:postgres@localhost:5433/edgehub}"
if command -v psql >/dev/null 2>&1; then
  if PGPASSWORD="${PGPASSWORD:-postgres}" psql "$PG_DSN" -c "SELECT 1;" >/dev/null 2>&1; then
    ok "Postgres" "$PG_DSN" "connected"
  else
    fail "Postgres" "$PG_DSN" "connection-failed"
  fi
else
  echo "psql not installed; skip DB check. On macOS: brew install libpq; export PATH to include /opt/homebrew/opt/libpq/bin"
fi