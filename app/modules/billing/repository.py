from app.shared.repository import SupabaseRepository, log_event


class BillingRepository:
    payments = SupabaseRepository("payments")
    subscriptions = SupabaseRepository("subscriptions")
    plans = SupabaseRepository("plans")
    credit_packages = SupabaseRepository("credit_packages")
    coupons = SupabaseRepository("coupons")

    def log(self, *args, **kwargs):
        return log_event(*args, **kwargs)
