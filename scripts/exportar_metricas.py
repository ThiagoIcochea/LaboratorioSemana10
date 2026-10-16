#!/usr/bin/env python3
"""
Exporta los datos reales del experimento desde la API HTTP de Prometheus.

Salidas en resultados/:
  series_experimento.csv  -> series temporales (paso 5 s) de todas las señales
  consultas_promql.json   -> cada consulta PromQL, su objetivo, periodo y resultado
  resumen_fases.csv       -> indicadores por fase (línea base / incidente / recuperación)
  alertas_api.json        -> estado de reglas de alerta al momento de exportar
"""
import argparse
import csv
import json
import time
from datetime import datetime, timezone, timedelta

import requests

LIMA = timezone(timedelta(hours=-5))

SERIES = {
    "up_app": 'up{job="catalogo-app"}',
    "up_node": 'up{job="node"}',
    "rps_total": 'sum(rate(app_http_requests_total[1m]))',
    "rps_2xx": 'sum(rate(app_http_requests_total{status=~"2.."}[1m]))',
    "rps_5xx": 'sum(rate(app_http_requests_total{status=~"5.."}[1m]))',
    "ratio_5xx": 'job:app_http_errors:ratio_rate1m',
    "lat_p50": 'histogram_quantile(0.50, sum by (le) (rate(app_http_request_duration_seconds_bucket[1m])))',
    "lat_p95": 'histogram_quantile(0.95, sum by (le) (rate(app_http_request_duration_seconds_bucket[1m])))',
    "lat_p99": 'histogram_quantile(0.99, sum by (le) (rate(app_http_request_duration_seconds_bucket[1m])))',
    "lat_media": 'sum(rate(app_http_request_duration_seconds_sum[1m])) / sum(rate(app_http_request_duration_seconds_count[1m]))',
    "dep_p95": 'job:app_dependency_latency_seconds:p95_1m',
    "dep_err_rps": 'sum(rate(app_dependency_errors_total[1m]))',
    "inflight": 'app_http_inflight_requests',
    "cpu_host": '1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))',
    "cpu_proc_app": 'rate(process_cpu_seconds_total{job="catalogo-app"}[1m])',
    "load1": 'node_load1',
    "mem_disp_ratio": 'node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes',
    "rss_app_mb": 'process_resident_memory_bytes{job="catalogo-app"} / 1024 / 1024',
    "disk_io_util": 'max(rate(node_disk_io_time_seconds_total[1m]))',
    "fault_flag": 'app_fault_injection_active',
    "alertas_firing": 'count(ALERTS{alertstate="firing"}) or vector(0)',
}


def q(prom, expr, t):
    r = requests.get(f"{prom}/api/v1/query", params={"query": expr, "time": t}, timeout=30).json()
    if r["status"] != "success":
        raise RuntimeError(f"{expr}: {r}")
    return r["data"]["result"]


def qr(prom, expr, start, end, step=5):
    r = requests.get(f"{prom}/api/v1/query_range",
                     params={"query": expr, "start": start, "end": end, "step": step}, timeout=60).json()
    if r["status"] != "success":
        raise RuntimeError(f"{expr}: {r}")
    return r["data"]["result"]


def scalar(res):
    if not res:
        return None
    return float(res[0]["value"][1])


def iso(t):
    return datetime.fromtimestamp(t, LIMA).strftime("%Y-%m-%d %H:%M:%S")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prom", default="http://localhost:9090")
    ap.add_argument("--timeline", default="resultados/timeline.csv")
    ap.add_argument("--out", default="resultados")
    a = ap.parse_args()

    ev = {}
    with open(a.timeline) as f:
        for row in csv.DictReader(f):
            ev[row["evento"]] = int(row["timestamp_unix"])
    fases = {
        "linea_base": (ev["baseline_inicio"], ev["baseline_fin"]),
        "incidente": (ev["incidente_inicio"], ev["incidente_fin"]),
        "recuperacion": (ev["recuperacion_inicio"], ev["recuperacion_fin"]),
    }
    start = ev.get("calentamiento_inicio", ev["baseline_inicio"]) - 30
    end = ev["recuperacion_fin"] + 30

    # 1) Series temporales
    cols = {}
    for name, expr in SERIES.items():
        res = qr(a.prom, expr, start, end)
        cols[name] = {int(float(t)): float(v) for t, v in (res[0]["values"] if res else [])}
    ts_all = sorted(set().union(*[set(c) for c in cols.values()]))
    with open(f"{a.out}/series_experimento.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_unix", "hora_lima"] + list(SERIES))
        for t in ts_all:
            w.writerow([t, iso(t)] + [("" if cols[n].get(t) is None else round(cols[n][t], 6)) for n in SERIES])

    # 2) Consultas PromQL documentadas, evaluadas por fase
    consultas = []

    def registrar(cid, objetivo, expr, fase, t_eval, ventana, tipo="instant"):
        res = q(a.prom, expr, t_eval)
        consultas.append({
            "id": cid, "objetivo": objetivo, "promql": expr, "fase": fase,
            "evaluado_en": iso(t_eval), "ventana": ventana,
            "resultado": [{"labels": r["metric"], "valor": float(r["value"][1])} for r in res],
        })
        return res

    resumen = []
    for fase, (t0, t1) in fases.items():
        d = t1 - t0
        w = f"{d}s"
        fila = {"fase": fase, "inicio_lima": iso(t0), "fin_lima": iso(t1), "duracion_s": d}
        fila["disponibilidad_min_up"] = scalar(registrar(
            "Q1", "Disponibilidad del objetivo: mínimo de up en la fase",
            f'min_over_time(up{{job="catalogo-app"}}[{w}])', fase, t1, w))
        fila["peticiones_totales"] = scalar(registrar(
            "Q2a", "Peticiones atendidas en la fase (incremento del contador)",
            f'sum(increase(app_http_requests_total[{w}]))', fase, t1, w))
        fila["rps_promedio"] = scalar(registrar(
            "Q2b", "Tasa media de peticiones por segundo en la fase",
            f'sum(rate(app_http_requests_total[{w}]))', fase, t1, w))
        registrar("Q2c", "Tasa por endpoint y código de estado",
                  f'sum by (endpoint, status) (rate(app_http_requests_total[{w}]))', fase, t1, w)
        fila["ratio_errores_5xx"] = scalar(registrar(
            "Q3", "Proporción de respuestas 5xx en la fase",
            f'sum(increase(app_http_requests_total{{status=~"5.."}}[{w}])) / sum(increase(app_http_requests_total[{w}]))',
            fase, t1, w))
        fila["latencia_media_s"] = scalar(registrar(
            "Q4a", "Latencia media HTTP en la fase",
            f'sum(rate(app_http_request_duration_seconds_sum[{w}])) / sum(rate(app_http_request_duration_seconds_count[{w}]))',
            fase, t1, w))
        fila["latencia_p95_s"] = scalar(registrar(
            "Q4b", "Percentil 95 de latencia HTTP en toda la fase",
            f'histogram_quantile(0.95, sum by (le) (rate(app_http_request_duration_seconds_bucket[{w}])))',
            fase, t1, w))
        registrar("Q4c", "p95 de latencia por endpoint (agrupación by)",
                  f'histogram_quantile(0.95, sum by (endpoint, le) (rate(app_http_request_duration_seconds_bucket[{w}])))',
                  fase, t1, w)
        fila["latencia_p95_max_1m_s"] = scalar(registrar(
            "Q5", "Máximo temporal del p95 (ventana 1 m) dentro de la fase",
            f'max_over_time(job:app_http_latency_seconds:p95_1m[{w}])', fase, t1, w))
        fila["dependencia_p95_s"] = scalar(registrar(
            "Q6", "p95 de latencia de inventario-db en la fase",
            f'histogram_quantile(0.95, sum by (le) (rate(app_dependency_duration_seconds_bucket[{w}])))',
            fase, t1, w))
        fila["dependencia_errores"] = scalar(registrar(
            "Q7", "Errores de la dependencia (incremento) por motivo",
            f'sum(increase(app_dependency_errors_total[{w}])) or vector(0)', fase, t1, w))
        fila["cpu_host_media"] = scalar(registrar(
            "Q8a", "Uso medio de CPU del host (1 - idle), avg por instancia",
            f'1 - avg by (instance) (rate(node_cpu_seconds_total{{mode="idle"}}[{w}]))', fase, t1, w))
        fila["cpu_host_max_1m"] = scalar(registrar(
            "Q8b", "Máximo del uso de CPU del host (ventanas de 1 m) en la fase",
            f'max_over_time((1 - avg(rate(node_cpu_seconds_total{{mode="idle"}}[1m])))[{w}:5s])', fase, t1, w))
        fila["cpu_proceso_app_nucleos"] = scalar(registrar(
            "Q8c", "CPU consumida por el proceso de la app (núcleos)",
            f'rate(process_cpu_seconds_total{{job="catalogo-app"}}[{w}])', fase, t1, w))
        fila["mem_disponible_min_ratio"] = scalar(registrar(
            "Q9a", "Mínimo de memoria disponible del host (ratio)",
            f'min_over_time((node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)[{w}:5s])', fase, t1, w))
        fila["rss_app_max_mb"] = scalar(registrar(
            "Q9b", "Máximo de memoria residente de la app (MB)",
            f'max_over_time(process_resident_memory_bytes{{job="catalogo-app"}}[{w}]) / 1024 / 1024', fase, t1, w))
        fila["inflight_max"] = scalar(registrar(
            "Q10", "Concurrencia máxima (peticiones en curso)",
            f'max_over_time(app_http_inflight_requests[{w}])', fase, t1, w))
        fila["disk_io_util_max"] = scalar(registrar(
            "Q11", "Máxima utilización de E/S de disco (fracción de tiempo ocupado)",
            f'max_over_time(max(rate(node_disk_io_time_seconds_total[1m]))[{w}:5s])', fase, t1, w))
        fila["alertas_disparadas"] = sorted({r["metric"].get("alertname") for r in registrar(
            "Q12", "Alertas en estado firing durante la fase",
            f'max_over_time(ALERTS{{alertstate="firing"}}[{w}])', fase, t1, w)})
        resumen.append(fila)

    with open(f"{a.out}/consultas_promql.json", "w", encoding="utf-8") as f:
        json.dump(consultas, f, indent=2, ensure_ascii=False)
    with open(f"{a.out}/resumen_fases.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(resumen[0]))
        w.writeheader()
        for r in resumen:
            r = dict(r)
            r["alertas_disparadas"] = ";".join(x for x in r["alertas_disparadas"] if x)
            w.writerow(r)

    # 3) Primer instante de disparo de cada alerta (estado firing) en el experimento
    firing = qr(a.prom, 'ALERTS{alertstate="firing"}', start, end, 5)
    pending = qr(a.prom, 'ALERTS{alertstate="pending"}', start, end, 5)
    trans = []
    for state, res in (("pending", pending), ("firing", firing)):
        for s in res:
            ts = [int(float(t)) for t, _ in s["values"]]
            trans.append({"alerta": s["metric"]["alertname"], "estado": state,
                          "primero": iso(min(ts)), "ultimo": iso(max(ts)),
                          "primero_unix": min(ts), "ultimo_unix": max(ts)})
    with open(f"{a.out}/alertas_transiciones.json", "w", encoding="utf-8") as f:
        json.dump(sorted(trans, key=lambda x: x["primero_unix"]), f, indent=2, ensure_ascii=False)
    rules = requests.get(f"{a.prom}/api/v1/rules", timeout=30).json()
    with open(f"{a.out}/alertas_api.json", "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)
    print(f"Exportadas {len(ts_all)} marcas temporales, {len(consultas)} consultas, {len(trans)} transiciones de alertas")


if __name__ == "__main__":
    main()
