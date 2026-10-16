#!/usr/bin/env bash
# Variables comunes. Pueden sobrescribirse por entorno.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_URL="${APP_URL:-http://localhost:8000}"
PROM_URL="${PROM_URL:-http://localhost:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
RPS="${RPS:-8}"
RES="$ROOT/resultados"
TIMELINE="$RES/timeline.csv"
mkdir -p "$RES"
[ -f "$TIMELINE" ] || echo "evento,timestamp_unix,iso_utc,iso_lima" > "$TIMELINE"

marca() {  # marca <evento>
  local ts; ts=$(date +%s)
  echo "$1,$ts,$(date -u -d @"$ts" +%FT%TZ),$(TZ=America/Lima date -d @"$ts" +%FT%T%:z)" >> "$TIMELINE"
  echo "[$(TZ=America/Lima date +%T)] $1"
}

fault() {  # fault on|off
  local en=0; [ "$1" = "on" ] && en=1
  curl -fsS -X POST -H "X-Fault-Token: ${FAULT_TOKEN:-}" "$APP_URL/admin/fault?enable=$en"; echo
}
