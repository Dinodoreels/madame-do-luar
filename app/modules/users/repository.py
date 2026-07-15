import requests as http

import db_client
from app.shared.repository import SupabaseRepository, audit_event, log_event


class UsersRepository:
    users = SupabaseRepository("users")
    questions = SupabaseRepository("questions")
    daily_cards = SupabaseRepository("daily_cards")
    messages = SupabaseRepository("message_events")
    payments = SupabaseRepository("payments")
    credit_transactions = SupabaseRepository("credit_transactions")

    def count(self, table: str, filters: str = "") -> int:
        try:
            url, headers = db_client.get_supabase_headers()
            r = http.get(
                f"{url}/rest/v1/{table}?select=*&{filters}" if filters else f"{url}/rest/v1/{table}?select=*",
                headers={**headers, "Prefer": "count=exact"},
                timeout=10,
            )
            return int(r.headers.get("content-range", "0/0").split("/")[-1])
        except Exception:
            return 0

    def active_subscription(self, user_id: str):
        try:
            url, headers = db_client.get_supabase_headers()
            r = http.get(
                f"{url}/rest/v1/subscriptions"
                f"?user_id=eq.{user_id}&status=eq.ativo&order=renovacao.desc&limit=1&select=*",
                headers=headers,
                timeout=10,
            )
            data = r.json()
            return data[0] if isinstance(data, list) and data else None
        except Exception:
            return None

    def export_user_data(self, user_id: str):
        return db_client.exportar_dados_usuario(user_id)

    def anonymize_user(self, user_id: str, reason: str | None = None):
        return db_client.anonimizar_usuario(user_id, reason=reason)

    def update_user(self, user_id: str, **payload):
        return db_client.atualizar_usuario(user_id, **payload)

    def change_password(self, user_id: str, current_password: str, new_password: str):
        return db_client.alterar_senha(user_id, current_password, new_password)

    def log(self, *args, **kwargs):
        return log_event(*args, **kwargs)

    def audit(self, *args, **kwargs):
        return audit_event(*args, **kwargs)
