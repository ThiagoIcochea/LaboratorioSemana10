#!/usr/bin/env python3
"""
Generador de tráfico controlado (solo contra la app local del laboratorio).

Uso: python3 scripts/loadgen.py --url http://localhost:8000 --rps 8 --duration 360 --out resultados/cliente.csv
Mezcla: 70 % GET /api/productos, 20 % POST /api/checkout, 10 % GET /
Registra en CSV la vista del cliente: timestamp, endpoint, status, latencia.
"""
import argparse
import csv
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

MIX = [("GET", "/api/productos", 0.70), ("POST", "/api/checkout", 0.20), ("GET", "/", 0.10)]


def pick():
    r, acc = random.random(), 0.0
    for m, p, w in MIX:
        acc += w
        if r <= acc:
            return m, p
    return MIX[-1][:2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--rps", type=float, default=8)
    ap.add_argument("--duration", type=int, default=60)
    ap.add_argument("--out", default=None)
    ap.add_argument("--timeout", type=float, default=5.0)
    a = ap.parse_args()

    lock = threading.Lock()
    rows = []
    session = requests.Session()

    def hit(method, path):
        t0 = time.time()
        try:
            r = session.request(method, a.url + path, timeout=a.timeout)
            status = r.status_code
        except requests.RequestException:
            status = 0  # timeout del cliente / conexión
        with lock:
            rows.append((round(t0, 3), path, status, round(time.time() - t0, 4)))

    interval = 1.0 / a.rps
    end = time.time() + a.duration
    nxt = time.time()
    with ThreadPoolExecutor(max_workers=64) as pool:
        while time.time() < end:
            pool.submit(hit, *pick())
            nxt += interval
            time.sleep(max(0, nxt - time.time()))

    ok = sum(1 for r in rows if r[2] == 200)
    print(f"peticiones={len(rows)} ok={ok} error={len(rows) - ok} "
          f"lat_media={sum(r[3] for r in rows) / max(1, len(rows)):.3f}s")
    if a.out:
        new = False
        try:
            open(a.out).close()
        except FileNotFoundError:
            new = True
        with open(a.out, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp_unix", "endpoint", "status", "latencia_s"])
            w.writerows(sorted(rows))


if __name__ == "__main__":
    main()
