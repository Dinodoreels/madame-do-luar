from app.shared.repository import SupabaseRepository, log_event


class NotificationsRepository:
    message_events = SupabaseRepository("message_events")
    notification_logs = SupabaseRepository("notification_logs")
    users = SupabaseRepository("users")

    def log(self, *args, **kwargs):
        return log_event(*args, **kwargs)
