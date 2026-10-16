#!/usr/bin/env python3
"""
Captura pantallas REALES de la interfaz web de Prometheus (Chromium headless).
Uso: python3 scripts/capturas_prometheus.py [--prom http://localhost:9090]
Si no hay timeline, solo captura targets/reglas/alertas.
"""
import argparse
import csv
import pathlib
import urllib.parse
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
EV = ROOT / "evidencias"


def graph_url(prom, expr, end_ts, rng):
    end = datetime.fromtimestamp(end_ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    p = {"g0.expr": expr, "g0.tab": "graph", "g0.display_mode": "lines", "g0.show_exemplars": "0",
         "g0.range_input": rng, "g0.end_input": end, "g0.moment_input": end}
    if "ALERTS" in expr:
        p["g0.stacked"] = "1"
    return f"{prom}/query?" + urllib.parse.urlencode(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prom", default="http://localhost:9090")
    a = ap.parse_args()
    tl = ROOT / "resultados/timeline.csv"
    ev = {r["evento"]: int(r["timestamp_unix"]) for r in csv.DictReader(open(tl))} if tl.exists() else {}

    shots = [
        (f"{a.prom}/targets", EV / "arquitectura/prometheus_targets.png", 900),
        (f"{a.prom}/rules", EV / "alertas/prometheus_reglas.png", 1500),
        (f"{a.prom}/alerts?showEmptyGroups=0", EV / "alertas/prometheus_alertas.png", 1100),
    ]
    if "recuperacion_fin" in ev:
        end = ev["recuperacion_fin"] + 60
        span = f"{(end - ev['baseline_inicio']) // 60 + 2}m"
        G = [
            ('up', "baseline/prom_up.png"),
            ('sum by (status) (rate(app_http_requests_total[1m]))', "consultas/prom_rps_por_estado.png"),
            ('job:app_http_errors:ratio_rate1m', "incidente/prom_ratio_errores.png"),
            ('histogram_quantile(0.95, sum by (le) (rate(app_http_request_duration_seconds_bucket[1m])))',
             "incidente/prom_latencia_p95.png"),
            ('job:app_dependency_latency_seconds:p95_1m', "incidente/prom_dependencia_p95.png"),
            ('1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))', "incidente/prom_cpu_host.png"),
            ('node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes', "incidente/prom_memoria_host.png"),
            ('max_over_time(job:app_http_latency_seconds:p95_1m[5m])', "consultas/prom_max_over_time_p95.png"),
            ('sum by (alertstate) (ALERTS)', "alertas/prom_series_alerts.png"),
        ]
        for expr, out in G:
            shots.append((graph_url(a.prom, expr, end, span), EV / out, 820))
        # Vistas por fase (misma consulta, ventana de cada fase)
        for fase, (i, f) in {"baseline": ("baseline_inicio", "baseline_fin"),
                             "incidente": ("incidente_inicio", "incidente_fin"),
                             "recuperacion": ("recuperacion_inicio", "recuperacion_fin")}.items():
            rng = f"{(ev[f] - ev[i]) // 60}m"
            shots.append((graph_url(a.prom, 'job:app_http_latency_seconds:p95_1m', ev[f], rng),
                          EV / f"{fase}/prom_p95_{fase}.png", 820))

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=1.25,
                        timezone_id="America/Lima", locale="es-PE")
        for url, out, h in shots:
            pg.set_viewport_size({"width": 1400, "height": h})
            pg.goto(url, wait_until="load")
            pg.wait_for_timeout(4000)
            out.parent.mkdir(parents=True, exist_ok=True)
            pg.screenshot(path=str(out), full_page=False)
            print("  ", out.relative_to(ROOT))
        b.close()


if __name__ == "__main__":
    main()
