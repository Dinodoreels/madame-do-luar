from app.shared.repository import SupabaseRepository, log_event


class AnalyticsRepository:
    events = SupabaseRepository("analytics_events")
    system_logs = SupabaseRepository("system_logs")

    def create_event(self, payload: dict):
        return self.events.create(payload)

    def list_events(self, *, filters: str = "", limit: int = 5000, order: str = "created_at.desc"):
        return self.events.list(select="*", filters=filters, limit=limit, order=order, timeout=8)

    def log(self, *args, **kwargs):
        return log_event(*args, **kwargs)
