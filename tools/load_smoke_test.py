"""
Teste leve de carga/smoke para endpoints publicos.

Uso:
  python tools/load_smoke_test.py --base-url http://127.0.0.1:8000 --requests 40 --concurrency 8
"""

from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


DEFAULT_PATHS = ["/", "/termos.html", "/privacidade.html", "/ia.html", "/pagamento/sucesso/"]


def hit(base_url: str, path: str) -> tuple[bool, float, str]:
    started = time.perf_counter()
    try:
        response = requests.get(base_url.rstrip("/") + path, timeout=15)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return response.status_code < 500, elapsed_ms, f"{path} HTTP {response.status_code}"
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return False, elapsed_ms, f"{path} {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga leve para readiness.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=40)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--max-p95-ms", type=int, default=2500)
    args = parser.parse_args()

    paths = [DEFAULT_PATHS[index % len(DEFAULT_PATHS)] for index in range(max(args.requests, 1))]
    results = []
    with ThreadPoolExecutor(max_workers=max(args.concurrency, 1)) as executor:
        futures = [executor.submit(hit, args.base_url, path) for path in paths]
        for future in as_completed(futures):
            results.append(future.result())

    failures = [message for ok, _, message in results if not ok]
    latencies = [elapsed for _, elapsed, _ in results]
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)
    avg = statistics.mean(latencies)

    print(f"requests={len(results)} failures={len(failures)} avg_ms={avg:.0f} p95_ms={p95:.0f}")
    if failures:
        print("Falhas:")
        for failure in failures[:10]:
            print(f"- {failure}")
        return 1
    if p95 > args.max_p95_ms:
        print(f"p95 acima do limite: {p95:.0f}ms > {args.max_p95_ms}ms")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
