from app.shared.repository import SupabaseRepository, log_event
from app.shared.repository import audit_event

import db_client


class AutomationRepository:
    rules = SupabaseRepository("automation_rules")
    steps = SupabaseRepository("automation_steps")
    message_events = SupabaseRepository("message_events")
    reprocess_queue = SupabaseRepository("reprocess_queue")
    readings = SupabaseRepository("readings")
    alerts = SupabaseRepository("internal_alerts")

    def log(self, *args, **kwargs):
        return log_event(*args, **kwargs)

    def audit(self, *args, **kwargs):
        return audit_event(*args, **kwargs)

    def enqueue(self, type_: str, payload: dict, related_payment_id: str | None = None, related_reading_id: str | None = None, error_message: str | None = None):
        return db_client.enfileirar_reprocessamento(type_, payload, related_payment_id=related_payment_id, related_reading_id=related_reading_id, error_message=error_message)

    def list_jobs(self, filters: str = "", limit: int = 100, order: str = "scheduled_at.asc"):
        return self.reprocess_queue.list(filters=filters, limit=limit, order=order)

    def get_job(self, queue_id: str):
        return self.reprocess_queue.get_by_id("queue_id", queue_id)

    def update_job(self, queue_id: str, payload: dict):
        return self.reprocess_queue.update("queue_id", queue_id, payload)

    def create_alert(self, *args, **kwargs):
        return db_client.criar_alerta_unico(*args, **kwargs)
