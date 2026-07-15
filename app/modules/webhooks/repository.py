import db_client
from app.shared.repository import SupabaseRepository, log_event


class WebhooksRepository:
    payments = SupabaseRepository("payments")
    events = SupabaseRepository("payment_webhook_events")

    def get_payment_by_transaction(self, transaction_id: str):
        return db_client.buscar_pagamento_por_transacao(transaction_id)

    def register_payment_webhook(self, **kwargs):
        return db_client.registrar_webhook_pagamento(**kwargs)

    def approve_pix_payment(self, payment_id: str, payload: dict):
        return db_client.aprovar_pagamento_pix(payment_id, webhook_payload=payload)

    def update_payment(self, payment_id: str, payload: dict):
        return self.payments.update("payment_id", payment_id, payload)

    def mark_event_processed(self, event_id: str, payload: dict):
        return self.events.update("event_id", event_id, payload)

    def log(self, *args, **kwargs):
        return log_event(*args, **kwargs)
