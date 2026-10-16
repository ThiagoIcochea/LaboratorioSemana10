"""
Aplicación web de prueba instrumentada para Prometheus.

Simula una tienda ("catalogo") que consulta una dependencia interna
(inventario-db). Expone métricas en /metrics y permite activar un
modo de fallo CONTROLADO y REVERSIBLE que degrada únicamente a la
dependencia simulada (latencia alta + errores intermitentes).

El fallo NO consume CPU: la latencia se introduce con time.sleep(),
lo que permite contrastar la hipótesis de "saturación de CPU" con datos.
"""
import os
import random
import threading
import time

from flask import Flask, Response, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)

app = Flask(__name__)

# ----------------------------------------------------------------------------
# Métricas
# ----------------------------------------------------------------------------
REQUESTS = Counter(
    "app_http_requests_total",
    "Total de peticiones HTTP atendidas por la aplicación",
    ["method", "endpoint", "status"],
)
LATENCY = Histogram(
    "app_http_request_duration_seconds",
    "Duración de las peticiones HTTP (segundos)",
    ["endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.5, 5.0),
)
INFLIGHT = Gauge(
    "app_http_inflight_requests",
    "Peticiones HTTP en curso (concurrencia instantánea)",
)
DEP_LATENCY = Histogram(
    "app_dependency_duration_seconds",
    "Duración de las llamadas a la dependencia interna (segundos)",
    ["dependency"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 1.5, 2.5),
)
DEP_ERRORS = Counter(
    "app_dependency_errors_total",
    "Errores en llamadas a la dependencia interna",
    ["dependency", "reason"],
)
FAULT_MODE = Gauge(
    "app_fault_injection_active",
    "1 si el modo de fallo controlado está activo (marcador del experimento)",
)
BUILD = Info("app_build", "Información de la aplicación de prueba")
BUILD.info({"version": "1.0.0", "service": "catalogo"})

DEPENDENCY = "inventario-db"
FAULT_TOKEN = os.environ.get("FAULT_TOKEN", "")

_state = {"fault": False, "since": None}
_lock = threading.Lock()


def call_dependency():
    """Simula la consulta a la dependencia. Lanza RuntimeError si falla."""
    with _lock:
        fault = _state["fault"]
    start = time.perf_counter()
    try:
        if fault:
            # Degradación: latencia alta y 30 % de timeouts
            time.sleep(random.uniform(0.6, 1.4))
            if random.random() < 0.30:
                DEP_ERRORS.labels(DEPENDENCY, "timeout").inc()
                raise RuntimeError("timeout en inventario-db")
        else:
            time.sleep(random.uniform(0.008, 0.035))
            if random.random() < 0.002:
                DEP_ERRORS.labels(DEPENDENCY, "transient").inc()
                raise RuntimeError("error transitorio")
    finally:
        DEP_LATENCY.labels(DEPENDENCY).observe(time.perf_counter() - start)


def instrumented(endpoint):
    def deco(fn):
        def wrapper(*a, **kw):
            INFLIGHT.inc()
            start = time.perf_counter()
            status = 500
            try:
                resp = fn(*a, **kw)
                status = resp[1] if isinstance(resp, tuple) else 200
                return resp
            finally:
                LATENCY.labels(endpoint).observe(time.perf_counter() - start)
                REQUESTS.labels(request.method, endpoint, str(status)).inc()
                INFLIGHT.dec()

        wrapper.__name__ = fn.__name__
        return wrapper

    return deco


@app.route("/")
@instrumented("/")
def index():
    return jsonify(service="catalogo", status="ok"), 200


@app.route("/api/productos")
@instrumented("/api/productos")
def productos():
    try:
        call_dependency()
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 503
    # trabajo ligero de CPU (serialización)
    items = [{"id": i, "nombre": f"producto-{i}", "stock": random.randint(0, 50)} for i in range(20)]
    return jsonify(items=items), 200


@app.route("/api/checkout", methods=["POST"])
@instrumented("/api/checkout")
def checkout():
    try:
        call_dependency()
        call_dependency()  # reserva + confirmación de stock
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 503
    return jsonify(orden=random.randint(1000, 9999), estado="confirmada"), 200


@app.route("/health")
def health():
    # Liveness: no depende de inventario-db
    return jsonify(status="up"), 200


@app.route("/admin/fault", methods=["GET", "POST"])
def fault():
    if FAULT_TOKEN and request.headers.get("X-Fault-Token") != FAULT_TOKEN:
        return jsonify(error="no autorizado"), 403
    if request.method == "POST":
        enable = str(request.args.get("enable", "")).lower() in ("1", "true", "on")
        with _lock:
            _state["fault"] = enable
            _state["since"] = time.time()
        FAULT_MODE.set(1 if enable else 0)
    with _lock:
        return jsonify(fault=_state["fault"], since=_state["since"]), 200


@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), threaded=True)
