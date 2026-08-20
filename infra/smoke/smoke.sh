#!/usr/bin/env bash
# Smoke test del despliegue coordinado (US8).
# Requiere: python3 con urllib (imagen stats-api) y variables STATS_API_URL / STATS_WEB_URL.
set -euo pipefail

API="${STATS_API_URL:-http://api:8000}"
WEB="${STATS_WEB_URL:-http://web:3000}"

http_ok() {
  python3 - "$1" <<'PY'
import sys, urllib.request
try:
    code = urllib.request.urlopen(sys.argv[1], timeout=10).status
except Exception as exc:
    print(f"FALLO HTTP: {exc}")
    sys.exit(1)
sys.exit(0 if code == 200 else 1)
PY
}

echo "== Smoke: liveness del API =="
http_ok "$API/api/v1/health/live"

echo "== Smoke: readiness del API =="
http_ok "$API/api/v1/health/ready"

echo "== Smoke: jornada con partidos =="
MATCHES=$(python3 - "$API/api/v1/matchdays/current" <<'PY'
import sys, json, urllib.request
data = json.load(urllib.request.urlopen(sys.argv[1], timeout=10))
print(len(data["matches"]))
PY
)
if [ "${MATCHES:-0}" -le 0 ]; then
  echo "FALLO: la jornada no devuelve partidos"
  exit 1
fi
echo "  partidos: $MATCHES"

echo "== Smoke: métricas operativas =="
http_ok "$API/api/v1/ops/metrics"

echo "== Smoke: web (home) =="
http_ok "$WEB/"

echo "== Smoke: web proxy a /api/v1 =="
http_ok "$WEB/api/v1/matchdays/current"

echo "SMOKE OK"
