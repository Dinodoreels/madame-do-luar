import db_client
from app.shared.repository import SupabaseRepository, log_event


class ReadingsRepository:
    daily_cards = SupabaseRepository("daily_cards")
    questions = SupabaseRepository("questions")
    readings = SupabaseRepository("readings")

    def has_daily_card_today(self, user_id: str) -> bool:
        return db_client.has_daily_card_today(user_id)

    def insert_daily_card(self, user_id: str, card_name: str, inverted: bool, message: str):
        return db_client.insert_daily_card(user_id, card_name, inverted, message)

    def reading_cost(self, reading_type: str) -> int:
        return db_client.obter_custo_leitura(reading_type)

    def consume_credits(self, **kwargs):
        return db_client.consumir_creditos(**kwargs)

    def refund_credits(self, *args, **kwargs):
        return db_client.estornar_creditos(*args, **kwargs)

    def link_credit_transaction(self, transaction_id: str, related_reading_id: str):
        return db_client.vincular_transacao_credito(transaction_id, related_reading_id=related_reading_id)

    def insert_question(self, user_id: str, question: str, tema: str):
        return db_client.insert_question(user_id, question, tema=tema)

    def insert_reading(self, **kwargs):
        return db_client.insert_reading(**kwargs)

    def mark_first_free_used(self, user_id: str):
        return db_client.marcar_primeira_tiragem_usada(user_id)

    def get_reading(self, reading_id: str):
        return self.readings.get_by_id("reading_id", reading_id)

    def get_question(self, question_id: str):
        return self.questions.get_by_id("question_id", question_id)

    def log(self, *args, **kwargs):
        return log_event(*args, **kwargs)
