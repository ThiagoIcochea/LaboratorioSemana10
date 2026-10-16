#!/usr/bin/env bash
# Ejecuta el experimento completo: línea base -> incidente -> recuperación -> exportación.
set -e
D="$(dirname "$0")"
bash "$D/validar_entorno.sh"
bash "$D/ejecutar_baseline.sh" "${BASELINE_S:-360}"
bash "$D/ejecutar_incidente.sh" "${INCIDENTE_S:-300}"
bash "$D/ejecutar_recuperacion.sh" "${RECUPERACION_S:-360}"
sleep 20   # deja que Prometheus recolecte las últimas muestras
bash "$D/exportar_metricas.sh"
