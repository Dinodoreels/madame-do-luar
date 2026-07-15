import db_client
from app.shared.repository import SupabaseRepository, log_event


class PaymentsRepository:
    payments = SupabaseRepository("payments")

    def apply_coupon(self, product: dict, coupon_code: str | None):
        return db_client.aplicar_cupom_produto(product, coupon_code)

    def create_payment(self, payload: dict):
        return self.payments.create(payload)

    def get_payment(self, payment_id: str):
        return self.payments.get_by_id("payment_id", payment_id)

    def get_user(self, user_id: str):
        return db_client.get_user_by_id(user_id)

    def log(self, *args, **kwargs):
        return log_event(*args, **kwargs)
