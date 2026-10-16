#!/usr/bin/env bash
# Exporta series y resultados de consultas PromQL del experimento a resultados/.
source "$(dirname "$0")/common.sh"
python3 "$ROOT/scripts/exportar_metricas.py" --prom "$PROM_URL" --timeline "$TIMELINE" --out "$RES"
