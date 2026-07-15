import os

import requests
from dotenv import load_dotenv


REQUIRED_COLUMNS = [
    "event_id",
    "event_name",
    "user_id",
    "admin_id",
    "session_id",
    "anonymous_id",
    "page_url",
    "referrer",
    "source",
    "entity_type",
    "entity_id",
    "metadata",
    "ip_address",
    "user_agent",
    "created_at",
]


def headers() -> tuple[str, dict]:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL e SUPABASE_KEY precisam estar definidos no .env.")
    return url.rstrip("/"), {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def check_select(url: str, headers_: dict, select: str) -> tuple[bool, str]:
    response = requests.get(f"{url}/rest/v1/analytics_events?select={select}&limit=1", headers=headers_, timeout=15)
    if response.status_code < 400:
        return True, "ok"
    try:
        data = response.json()
        return False, data.get("message") or response.text
    except Exception:
        return False, response.text


def main() -> None:
    url, headers_ = headers()
    checks = [("analytics_events", *check_select(url, headers_, "*"))]
    checks.extend((f"analytics_events.{column}", *check_select(url, headers_, column)) for column in REQUIRED_COLUMNS)
    ok = True
    for name, passed, detail in checks:
        status = "OK" if passed else "PENDENTE"
        print(f"- {status:8} {name}: {detail}")
        ok = ok and passed
    if not ok:
        raise SystemExit("\nMigration da Fase 8 ainda nao esta aplicada no Supabase.")
    print("\nMigration da Fase 8 aplicada e visivel pelo REST schema cache.")


if __name__ == "__main__":
    main()
