"""Genera grafana/dashboards/catalogo-observabilidad.json (dashboard provisionado)."""
import json
import pathlib

DS = {"type": "prometheus", "uid": "prometheus-lab"}
panels = []
pid = 0


def panel(title, exprs, unit, x, y, w=12, h=8, kind="timeseries", desc="", thresholds=None, minv=None, maxv=None):
    global pid
    pid += 1
    targets = [
        {"datasource": DS, "expr": e, "legendFormat": l, "refId": chr(65 + i)}
        for i, (e, l) in enumerate(exprs)
    ]
    defaults = {"unit": unit}
    if minv is not None:
        defaults["min"] = minv
    if maxv is not None:
        defaults["max"] = maxv
    if thresholds:
        defaults["thresholds"] = {"mode": "absolute", "steps": thresholds}
        if kind == "timeseries":
            defaults["custom"] = {"thresholdsStyle": {"mode": "line+area"}}
    p = {
        "id": pid,
        "type": kind,
        "title": title,
        "description": desc,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": targets,
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
    }
    panels.append(p)


GREEN_RED = lambda t: [{"color": "green", "value": None}, {"color": "red", "value": t}]

panel("Disponibilidad de objetivos (up)", [('up', '{{job}}')], "none", 0, 0, 8, 6, "stat",
      "1 = Prometheus alcanza el objetivo; 0 = caído", [{"color": "red", "value": None}, {"color": "green", "value": 1}])
panel("Modo de fallo inyectado (marcador del experimento)", [("app_fault_injection_active", "fault")], "none", 8, 0, 8, 6,
      "timeseries", "Marca declarada del experimento; no es una señal de diagnóstico", None, 0, 1)
panel("Peticiones en curso", [("app_http_inflight_requests", "in-flight")], "none", 16, 0, 8, 6)
panel("Peticiones por segundo por endpoint y estado",
      [('sum by (endpoint, status) (rate(app_http_requests_total[1m]))', '{{endpoint}} {{status}}')], "reqps", 0, 6)
panel("Tasa de errores 5xx (ratio)", [("job:app_http_errors:ratio_rate1m", "ratio 5xx")], "percentunit", 12, 6,
      thresholds=GREEN_RED(0.05), minv=0)
panel("Latencia HTTP p50 / p95 / p99",
      [("histogram_quantile(0.50, sum by (le) (rate(app_http_request_duration_seconds_bucket[1m])))", "p50"),
       ("histogram_quantile(0.95, sum by (le) (rate(app_http_request_duration_seconds_bucket[1m])))", "p95"),
       ("histogram_quantile(0.99, sum by (le) (rate(app_http_request_duration_seconds_bucket[1m])))", "p99")],
      "s", 0, 14, thresholds=GREEN_RED(0.5), minv=0)
panel("Latencia p95 de la dependencia inventario-db", [("job:app_dependency_latency_seconds:p95_1m", "{{dependency}} p95")],
      "s", 12, 14, thresholds=GREEN_RED(0.25), minv=0)
panel("Errores de la dependencia por motivo",
      [("sum by (reason) (rate(app_dependency_errors_total[1m]))", "{{reason}}")], "reqps", 0, 22)
panel("CPU del host (node_exporter)",
      [('1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))', "CPU host usada"),
       ('rate(process_cpu_seconds_total{job="catalogo-app"}[1m])', "CPU proceso app (núcleos)")],
      "percentunit", 12, 22, thresholds=GREEN_RED(0.85), minv=0)
panel("Memoria",
      [("node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes", "Memoria disponible host (ratio)")],
      "percentunit", 0, 30, minv=0, maxv=1)
panel("Memoria residente del proceso app",
      [('process_resident_memory_bytes{job="catalogo-app"}', "RSS app")], "bytes", 12, 30)
panel("Alertas activas", [('ALERTS{alertstate="firing"}', "{{alertname}}")], "none", 0, 38, 24, 6)

dash = {
    "uid": "catalogo-obs",
    "title": "Catálogo - Observabilidad (Laboratorio UTP)",
    "tags": ["utp", "prometheus", "laboratorio"],
    "timezone": "browser",
    "schemaVersion": 39,
    "refresh": "10s",
    "time": {"from": "now-30m", "to": "now"},
    "panels": panels,
}
out = pathlib.Path(__file__).resolve().parents[1] / "grafana/dashboards/catalogo-observabilidad.json"
out.write_text(json.dumps(dash, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Dashboard escrito en {out} con {len(panels)} paneles")
