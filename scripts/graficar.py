#!/usr/bin/env python3
"""
Genera gráficos a partir de los datos REALES exportados de Prometheus
(resultados/series_experimento.csv). Cada gráfico sombrea las fases del
experimento definidas en resultados/timeline.csv.
"""
import csv
import pathlib
from datetime import datetime, timedelta, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[1]
RES = ROOT / "resultados"
LIMA = timezone(timedelta(hours=-5))
FUENTE = "Fuente: Prometheus v3.5.0 (API /api/v1/query_range, paso 5 s). Elaboración propia."

rows = list(csv.DictReader(open(RES / "series_experimento.csv")))
ev = {r["evento"]: int(r["timestamp_unix"]) for r in csv.DictReader(open(RES / "timeline.csv"))}
T = [datetime.fromtimestamp(int(r["timestamp_unix"]), LIMA) for r in rows]
dt = lambda k: datetime.fromtimestamp(ev[k], LIMA)


def col(name, scale=1.0):
    return [float(r[name]) * scale if r[name] not in ("", "NaN") else float("nan") for r in rows]


FASES = [("baseline_inicio", "baseline_fin", "#2E8B57", "Línea base"),
         ("incidente_inicio", "incidente_fin", "#C0392B", "Incidente"),
         ("recuperacion_inicio", "recuperacion_fin", "#2E6DB4", "Recuperación")]


def fases(ax, labels=True):
    for a, b, c, lab in FASES:
        ax.axvspan(dt(a), dt(b), color=c, alpha=0.08, lw=0)
        if labels:
            ax.text(dt(a) + (dt(b) - dt(a)) / 2, 1.01, lab, transform=ax.get_xaxis_transform(),
                    ha="center", va="bottom", fontsize=8.5, color=c, fontweight="bold")
    ax.axvline(dt("incidente_inicio"), color="#C0392B", ls="--", lw=1)
    ax.axvline(dt("incidente_fin"), color="#2E6DB4", ls="--", lw=1)


def estilo(ax, ylabel, title):
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=11, pad=16, loc="left")
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=LIMA))
    ax.spines[["top", "right"]].set_visible(False)


def guardar(fig, path, xlabel=True):
    if xlabel:
        fig.axes[-1].set_xlabel("Hora (America/Lima, UTC-5) — " + dt("baseline_inicio").strftime("%d/%m/%Y"))
    fig.text(0.01, 0.005, FUENTE, fontsize=7, color="#666")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)
    print("  ", path.relative_to(ROOT))


EV = ROOT / "evidencias"

# 1. Peticiones por segundo
fig, ax = plt.subplots(figsize=(10, 3.6))
ax.plot(T, col("rps_total"), label="Total", color="#333")
ax.plot(T, col("rps_2xx"), label="2xx", color="#2E8B57")
ax.plot(T, col("rps_5xx"), label="5xx", color="#C0392B")
fases(ax); estilo(ax, "peticiones/s", "Tasa de peticiones por código de estado — rate(app_http_requests_total[1m])")
ax.legend(loc="center left", fontsize=8); ax.set_ylim(bottom=0)
guardar(fig, EV / "consultas/fig_rps.png")

# 2. Tasa de errores
fig, ax = plt.subplots(figsize=(10, 3.4))
ax.plot(T, col("ratio_5xx", 100), color="#C0392B", label="% respuestas 5xx")
ax.axhline(5, color="#999", ls=":", lw=1.2, label="Umbral alerta 5 %")
fases(ax); estilo(ax, "% de peticiones", "Proporción de errores 5xx — job:app_http_errors:ratio_rate1m")
ax.legend(loc="upper left", fontsize=8); ax.set_ylim(bottom=0)
guardar(fig, EV / "consultas/fig_errores.png")

# 3. Latencia
fig, ax = plt.subplots(figsize=(10, 3.6))
for k, c, lab in (("lat_p50", "#2E6DB4", "p50"), ("lat_p95", "#E67E22", "p95"), ("lat_p99", "#C0392B", "p99")):
    ax.plot(T, col(k, 1000), color=c, label=lab)
ax.axhline(500, color="#999", ls=":", lw=1.2, label="Umbral alerta p95 = 500 ms")
fases(ax); estilo(ax, "milisegundos", "Latencia HTTP (percentiles) — histogram_quantile(…, app_http_request_duration_seconds_bucket)")
ax.legend(loc="upper left", fontsize=8); ax.set_ylim(bottom=0)
guardar(fig, EV / "consultas/fig_latencia.png")

# 4. Dependencia
fig, ax = plt.subplots(figsize=(10, 3.6))
ax.plot(T, col("dep_p95", 1000), color="#8E44AD", label="p95 inventario-db (ms)")
ax.axhline(250, color="#999", ls=":", lw=1.2, label="Umbral alerta 250 ms")
ax2 = ax.twinx()
ax2.plot(T, col("dep_err_rps"), color="#C0392B", alpha=0.7, label="errores/s inventario-db")
ax2.set_ylabel("errores/s"); ax2.set_ylim(bottom=0); ax2.spines[["top"]].set_visible(False)
fases(ax); estilo(ax, "milisegundos", "Dependencia inventario-db: latencia p95 y errores")
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8); ax.set_ylim(bottom=0)
guardar(fig, EV / "consultas/fig_dependencia.png")

# 5. Recursos
fig, axs = plt.subplots(3, 1, figsize=(10, 7.4), sharex=True)
axs[0].plot(T, col("cpu_host", 100), color="#333", label="CPU host usada (%)")
axs[0].plot(T, col("cpu_proc_app", 100), color="#E67E22", label="CPU proceso app (% de 1 núcleo)")
axs[0].axhline(85, color="#999", ls=":", lw=1.2, label="Umbral alerta 85 %")
axs[0].set_ylim(0, 100); fases(axs[0]); estilo(axs[0], "%", "CPU — node_cpu_seconds_total y process_cpu_seconds_total")
axs[0].legend(loc="upper left", fontsize=7.5)
axs[1].plot(T, col("mem_disp_ratio", 100), color="#2E6DB4", label="Memoria disponible host (%)")
axs[1].set_ylim(0, 100); fases(axs[1], False); estilo(axs[1], "%", "Memoria disponible — node_memory_MemAvailable_bytes / MemTotal")
axs[1].legend(loc="lower left", fontsize=7.5)
axs[2].plot(T, col("rss_app_mb"), color="#8E44AD", label="RSS app (MB)")
axs[2].set_ylim(bottom=0); fases(axs[2], False); estilo(axs[2], "MB", "Memoria residente del proceso — process_resident_memory_bytes")
axs[2].legend(loc="lower left", fontsize=7.5)
guardar(fig, EV / "consultas/fig_recursos.png")

# 6. Correlación de tres señales + marcador
fig, axs = plt.subplots(4, 1, figsize=(10, 8.4), sharex=True)
series = [("dep_p95", 1000, "#8E44AD", "ms", "Señal 1: p95 de inventario-db"),
          ("lat_p95", 1000, "#E67E22", "ms", "Señal 2: p95 de latencia HTTP"),
          ("ratio_5xx", 100, "#C0392B", "%", "Señal 3: % de respuestas 5xx"),
          ("cpu_host", 100, "#333", "%", "Señal 4 (contraste): CPU del host")]
for i, (ax, (k, s, c, u, t)) in enumerate(zip(axs, series)):
    ax.plot(T, col(k, s), color=c)
    ax.set_ylim(bottom=0)
    if k == "cpu_host":
        ax.set_ylim(0, 100)
    fases(ax, i == 0); estilo(ax, u, t)
guardar(fig, EV / "incidente/fig_correlacion_senales.png")

# 7. Concurrencia
fig, ax = plt.subplots(figsize=(10, 3.2))
ax.plot(T, col("inflight"), color="#16A085", label="peticiones en curso")
fases(ax); estilo(ax, "peticiones", "Concurrencia instantánea — app_http_inflight_requests")
ax.set_ylim(bottom=0); ax.legend(loc="upper left", fontsize=8)
guardar(fig, EV / "incidente/fig_inflight.png")

# 8. Disponibilidad
fig, ax = plt.subplots(figsize=(10, 2.6))
ax.step(T, col("up_app"), where="post", color="#2E8B57", label='up{job="catalogo-app"}')
ax.step(T, col("up_node"), where="post", color="#2E6DB4", ls="--", label='up{job="node"}')
ax.set_ylim(-0.1, 1.2); fases(ax); estilo(ax, "up (0/1)", "Disponibilidad de los objetivos de recolección — up")
ax.legend(loc="lower left", fontsize=8)
guardar(fig, EV / "baseline/fig_up.png")

# 9. Alertas
fig, ax = plt.subplots(figsize=(10, 2.6))
ax.step(T, col("alertas_firing"), where="post", color="#C0392B")
fases(ax); estilo(ax, "n.º alertas", 'Alertas en estado firing — count(ALERTS{alertstate="firing"})')
ax.set_ylim(bottom=0)
guardar(fig, EV / "alertas/fig_alertas.png")
