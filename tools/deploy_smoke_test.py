"""
Smoke test HTTP para ambiente publicado.

Uso:
  python tools/deploy_smoke_test.py --base-url https://madamedoluar.com.br
"""
import argparse
import sys

import requests


def check(base_url: str, path: str, expected: int = 200) -> tuple[bool, str]:
    url = base_url.rstrip("/") + path
    try:
        response = requests.get(url, timeout=20)
        ok = response.status_code == expected
        return ok, f"{path} -> HTTP {response.status_code}"
    except Exception as exc:
        return False, f"{path} -> {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test pos-deploy.")
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()

    checks = [
        ("/health/detailed", 200),
        ("/api/status", 200),
        ("/admin.html", 200),
        ("/privacidade.html", 200),
        ("/termos.html", 200),
    ]
    failed = []
    for path, expected in checks:
        ok, message = check(args.base_url, path, expected)
        print(f"[{'OK' if ok else 'FAIL'}] {message}")
        if not ok:
            failed.append(message)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
