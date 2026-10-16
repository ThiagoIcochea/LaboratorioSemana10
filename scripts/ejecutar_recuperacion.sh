#!/usr/bin/env bash
# Fase de recuperación: fallo desactivado, mismo tráfico, se verifica el retorno a la línea base.
source "$(dirname "$0")/common.sh"
DUR="${1:-360}"
fault off >/dev/null
marca recuperacion_inicio
python3 "$ROOT/scripts/loadgen.py" --url "$APP_URL" --rps "$RPS" --duration "$DUR" --out "$RES/cliente_recuperacion.csv"
marca recuperacion_fin
