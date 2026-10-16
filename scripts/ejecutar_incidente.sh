#!/usr/bin/env bash
# Fase 4: incidente controlado y reversible.
# Cambio introducido: se activa el modo de fallo de la dependencia simulada
# inventario-db (latencia 0.6-1.4 s + 30 % de timeouts). Mismo tráfico que la línea base.
source "$(dirname "$0")/common.sh"
DUR="${1:-300}"
trap 'fault off >/dev/null; marca fallo_desactivado_por_trap' INT TERM
marca incidente_inicio
fault on
python3 "$ROOT/scripts/loadgen.py" --url "$APP_URL" --rps "$RPS" --duration "$DUR" --out "$RES/cliente_incidente.csv"
fault off
marca incidente_fin
