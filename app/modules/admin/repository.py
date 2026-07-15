import requests as http

import db_client
from app.shared.repository import SupabaseRepository, audit_event, log_event


class AdminRepository:
    users = SupabaseRepository("users")
    readings = SupabaseRepository("readings")
    questions = SupabaseRepository("questions")
    payments = SupabaseRepository("payments")
    credit_transactions = SupabaseRepository("credit_transactions")
    logs = SupabaseRepository("system_logs")
    audit_logs = SupabaseRepository("audit_logs")
    plans = SupabaseRepository("plans")
    credit_packages = SupabaseRepository("credit_packages")
    coupons = SupabaseRepository("coupons")
    rituals = SupabaseRepository("rituals")
    ritual_purchases = SupabaseRepository("ritual_purchases")
    settings = SupabaseRepository("settings")
    alerts = SupabaseRepository("internal_alerts")
    reprocess_queue = SupabaseRepository("reprocess_queue")

    def raw_headers(self):
        return db_client.get_supabase_headers()

    def patch_user_status(self, user_id: str, status: str):
        url, headers = self.raw_headers()
        patch_headers = dict(headers)
        patch_headers["Prefer"] = "return=representation"
        r = http.patch(
            f"{url}/rest/v1/users?user_id=eq.{user_id}",
            headers=patch_headers,
            json={"status": status},
            timeout=10,
        )
        return r.json() if r.text else []

    def get_user(self, user_id: str):
        return db_client.get_user_by_id(user_id)

    def adjust_credits(self, **kwargs):
        return db_client.ajustar_creditos(**kwargs)

    def change_plan(self, **kwargs):
        return db_client.registrar_mudanca_plano(**kwargs)

    def log(self, *args, **kwargs):
        return log_event(*args, **kwargs)

    def audit(self, *args, **kwargs):
        return audit_event(*args, **kwargs)
