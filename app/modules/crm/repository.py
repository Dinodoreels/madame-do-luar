import db_client
from app.shared.repository import SupabaseRepository, log_event


class CrmRepository:
    users = SupabaseRepository("users")
    readings = SupabaseRepository("readings")
    questions = SupabaseRepository("questions")
    payments = SupabaseRepository("payments")
    messages = SupabaseRepository("message_events")
    notifications = SupabaseRepository("notification_logs")
    logs = SupabaseRepository("system_logs")
    notes = SupabaseRepository("admin_customer_notes")
    tags = SupabaseRepository("customer_tags")
    user_tags = SupabaseRepository("user_customer_tags")
    segments = SupabaseRepository("customer_segments")
    user_segments = SupabaseRepository("user_customer_segments")
    triggers = SupabaseRepository("segment_automation_triggers")

    def get_user(self, user_id: str):
        return db_client.get_user_by_id(user_id)

    def log(self, *args, **kwargs):
        return log_event(*args, **kwargs)
