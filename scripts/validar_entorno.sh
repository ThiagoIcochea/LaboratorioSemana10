#!/usr/bin/env bash
# Verifica herramientas, servicios, objetivos de Prometheus, reglas y Grafana.
source "$(dirname "$0")/common.sh"
ok(){ echo "  [OK]  $*"; }; ko(){ echo "  [FALLA] $*"; FALLAS=$((FALLAS+1)); }
FALLAS=0
echo "== Herramientas"
for t in docker python3 curl; do command -v $t >/dev/null && ok "$t: $($t --version 2>&1 | head -1)" || ko "$t no encontrado"; done
docker compose version >/dev/null 2>&1 && ok "$(docker compose version)" || echo "  [INFO] docker compose no disponible (modo local sin Docker)"
nproc | xargs -I{} echo "  [INFO] CPUs: {}"; free -h | awk '/Mem:/{print "  [INFO] Memoria total: "$2}'

echo "== Servicios"
curl -fsS "$APP_URL/health" >/dev/null && ok "App $APP_URL/health" || ko "App no responde"
curl -fsS "$APP_URL/metrics" | grep -q app_http_requests_total && ok "App expone /metrics" || ko "App sin métricas"
curl -fsS "$PROM_URL/-/ready" >/dev/null && ok "Prometheus listo ($(curl -fsS $PROM_URL/api/v1/status/buildinfo | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["version"])'))" || ko "Prometheus no listo"

echo "== Objetivos de Prometheus"
curl -fsS "$PROM_URL/api/v1/targets" | python3 -c '
import sys,json
for t in json.load(sys.stdin)["data"]["activeTargets"]:
    print(f"  [{t["health"].upper():5}] {t["labels"]["job"]:14} {t["scrapeUrl"]}  último scrape: {t["lastScrape"][:19]}  error: {t["lastError"] or "-"}")'

echo "== Muestras recientes"
curl -fsS "$PROM_URL/api/v1/query" --data-urlencode 'query=count(up==1)' | python3 -c 'import sys,json;r=json.load(sys.stdin)["data"]["result"];print("  objetivos up:",r[0]["value"][1] if r else 0)'
curl -fsS "$PROM_URL/api/v1/query" --data-urlencode 'query=time()-timestamp(up{job="catalogo-app"})' | python3 -c 'import sys,json;r=json.load(sys.stdin)["data"]["result"];print("  antigüedad última muestra app (s):",round(float(r[0]["value"][1]),1) if r else "sin datos")'

echo "== Reglas"
curl -fsS "$PROM_URL/api/v1/rules" | python3 -c '
import sys,json
for g in json.load(sys.stdin)["data"]["groups"]:
    for r in g["rules"]: print(f"  {g["name"]:16} {r["type"]:9} {r["name"]:42} {r.get("state", r["health"])}")'

echo "== Grafana"
if curl -fsS "$GRAFANA_URL/api/health" >/dev/null 2>&1; then ok "Grafana $(curl -fsS $GRAFANA_URL/api/health | python3 -c 'import sys,json;print(json.load(sys.stdin)["version"])')"
else echo "  [INFO] Grafana no accesible en $GRAFANA_URL"; fi
echo "== Fallas: $FALLAS"
exit $FALLAS
