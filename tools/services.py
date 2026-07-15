import os
from typing import Any, Optional

import db_client
from llm_client import chamar_madame_do_luar
from notificacoes import enviar_email


class ServiceError(Exception):
    """Erro controlado de servico para a API traduzir em resposta HTTP."""

    def __init__(self, message: str, code: str = "SERVICE_ERROR", status_code: int = 400, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class DatabaseService:
    def __getattr__(self, name: str):
        return getattr(db_client, name)


class AIService:
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def gerar_carta_do_dia(self, carta: dict[str, Any]) -> str:
        return chamar_madame_do_luar(
            prompt_base_path="prompts/carta_do_dia.md",
            carta=carta["nome"],
            invertida="true" if carta["invertida"] else "false",
        )

    def gerar_leitura_tres_cartas(self, pergunta: str, c_passado: dict[str, Any], c_presente: dict[str, Any], c_futuro: dict[str, Any]) -> str:
        return chamar_madame_do_luar(
            prompt_base_path="prompts/tres_cartas.md",
            pergunta=pergunta,
            carta_passado=c_passado["nome"],
            invertida_passado="true" if c_passado["invertida"] else "false",
            carta_presente=c_presente["nome"],
            invertida_presente="true" if c_presente["invertida"] else "false",
            carta_futuro=c_futuro["nome"],
            invertida_futuro="true" if c_futuro["invertida"] else "false",
        )


class PaymentService:
    def calcular_produto_pix(self, product_type: str, product_id: str) -> dict[str, Any]:
        produto = db_client.calcular_produto_pagamento(product_type, product_id)
        if "erro" in produto:
            raise ServiceError(produto["erro"], code="PAYMENT_PRODUCT_INVALID", status_code=400)
        return produto

    def registrar_pix(self, user_id: str, produto: dict[str, Any], cobranca: dict[str, Any], expires_at: str) -> dict[str, Any]:
        if cobranca.get("payment_id"):
            pagamento = db_client.buscar_por_id("payments", "payment_id", cobranca["payment_id"])
            if not pagamento:
                raise ServiceError("Pagamento Mercado Pago nao encontrado apos criacao do checkout.", code="PAYMENT_REGISTRATION_FAILED", status_code=400)
            return pagamento

        pagamento = db_client.registrar_tentativa_pagamento_pix(
            user_id=user_id,
            produto=produto,
            gateway=cobranca["gateway"],
            transaction_id=cobranca["transaction_id"],
            expires_at=cobranca.get("expires_at") or expires_at,
            qr_code_url=cobranca.get("qr_code_url"),
            pix_copy_paste=cobranca.get("pix_copy_paste"),
            checkout_url=cobranca.get("checkout_url"),
            gateway_payload=cobranca.get("payload"),
        )
        if "erro" in pagamento:
            raise ServiceError(pagamento["erro"], code="PAYMENT_REGISTRATION_FAILED", status_code=400)
        return pagamento


class NotificationService:
    def enviar_email(self, destinatario: str, assunto: str, corpo: str) -> None:
        enviar_email(destinatario, assunto, corpo)


class ReadingService:
    def __init__(self, database: DatabaseService, ai: AIService):
        self.database = database
        self.ai = ai

    def gerar_interpretacao_tres_cartas(self, pergunta: str, cartas: list[dict[str, Any]]) -> str:
        if len(cartas) < 3:
            raise ServiceError("Nao foi possivel sortear as cartas da leitura.", code="READING_CARDS_INVALID", status_code=500)
        return self.ai.gerar_leitura_tres_cartas(pergunta, cartas[0], cartas[1], cartas[2])
