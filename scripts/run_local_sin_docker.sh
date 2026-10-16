#!/usr/bin/env bash
# Alternativa sin Docker: ejecuta app, node_exporter y Prometheus como procesos.
# Se usó cuando el entorno de ejecución no permitía descargar imágenes de Docker Hub.
# Requiere los binarios oficiales de Prometheus y node_exporter (releases de GitHub)
# en $BIN_DIR. Grafana no se incluye en este modo.
set -e
source "$(dirname "$0")/common.sh"
BIN_DIR="${BIN_DIR:-/opt/lab}"
RUN="$ROOT/.local-run"; mkdir -p "$RUN/tsdb"
PROM="$BIN_DIR/prometheus-3.5.0.linux-amd64"
NODE="$BIN_DIR/node_exporter-1.9.1.linux-amd64"

sed -e 's#prometheus:9090#localhost:9090#' -e 's#app:8000#localhost:8000#' \
    -e 's#node-exporter:9100#localhost:9100#' -e "s#/etc/prometheus/alerts.yml#$ROOT/prometheus/alerts.yml#" \
    "$ROOT/prometheus/prometheus.yml" > "$RUN/prometheus.yml"

"$NODE/node_exporter" --web.listen-address=:9100 > "$RUN/node_exporter.log" 2>&1 &
echo $! > "$RUN/node_exporter.pid"
(cd "$ROOT/application" && gunicorn -w 1 --threads 32 -b 0.0.0.0:8000 --timeout 30 app:app) > "$RUN/app.log" 2>&1 &
echo $! > "$RUN/app.pid"
"$PROM/prometheus" --config.file="$RUN/prometheus.yml" --storage.tsdb.path="$RUN/tsdb" \
    --storage.tsdb.retention.time=2d --web.enable-lifecycle > "$RUN/prometheus.log" 2>&1 &
echo $! > "$RUN/prometheus.pid"
sleep 6
echo "Servicios iniciados: app :8000, node_exporter :9100, prometheus :9090"
