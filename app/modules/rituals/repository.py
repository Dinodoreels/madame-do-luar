import db_client
from app.shared.repository import SupabaseRepository, log_event


class RitualsRepository:
    rituals = SupabaseRepository("rituals")
    purchases = SupabaseRepository("ritual_purchases")
    questions = SupabaseRepository("questions")
    coupons = SupabaseRepository("coupons")

    def list_active_rituals(self, filters: str = "ativo=eq.true", limit: int = 100):
        return self.rituals.list(filters=filters, limit=limit)

    def get_ritual(self, ritual_id: str):
        return self.rituals.get_by_id("ritual_id", ritual_id)

    def list_purchases(self, filters: str, limit: int = 1, order: str | None = None):
        return self.purchases.list(filters=filters, limit=limit, order=order)

    def create_purchase(self, payload: dict):
        return self.purchases.create(payload)

    def update_purchase(self, purchase_id: str, payload: dict):
        return self.purchases.update("purchase_id", purchase_id, payload)

    def calculate_payment_product(self, ritual_id: str):
        return db_client.calcular_produto_pagamento("ritual", ritual_id)

    def apply_coupon(self, product: dict, coupon_code: str | None):
        return db_client.aplicar_cupom_produto(product, coupon_code)

    def atomic_credit_purchase(self, *args, **kwargs):
        return db_client.comprar_ritual_com_creditos(*args, **kwargs)

    def consume_credits(self, *args, **kwargs):
        return db_client.consumir_creditos(*args, **kwargs)

    def refund_credits(self, *args, **kwargs):
        return db_client.estornar_creditos(*args, **kwargs)

    def register_coupon_use(self, coupon_code: str, user_id: str):
        return db_client.registrar_uso_cupom(coupon_code, user_id=user_id)

    def get_coupon_by_code(self, code: str):
        return self.coupons.get_by_id("code", code)

    def log(self, *args, **kwargs):
        return log_event(*args, **kwargs)
