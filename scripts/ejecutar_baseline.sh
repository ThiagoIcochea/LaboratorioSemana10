#!/usr/bin/env bash
# Fase 3: línea base. Tráfico normal con el modo de fallo desactivado.
source "$(dirname "$0")/common.sh"
DUR="${1:-360}"
fault off >/dev/null
marca baseline_inicio
python3 "$ROOT/scripts/loadgen.py" --url "$APP_URL" --rps "$RPS" --duration "$DUR" --out "$RES/cliente_baseline.csv"
marca baseline_fin
