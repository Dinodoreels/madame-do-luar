import os

import db_client
from app.core.config import settings
from app.core.errors import erro_http
from sortear_cartas import sortear
from services import AIService, DatabaseService, ReadingService


database_service = DatabaseService()
ai_service = AIService()
reading_service = ReadingService(database_service, ai_service)


def sanitize_question(pergunta: str) -> str:
    texto = " ".join((pergunta or "").split())
    if len(texto) < settings.min_tarot_question_length:
        raise erro_http(400, "READING_QUESTION_TOO_SHORT", f"Pergunta deve ter pelo menos {settings.min_tarot_question_length} caracteres.")
    if len(texto) > settings.max_tarot_question_length:
        raise erro_http(400, "READING_QUESTION_TOO_LONG", f"Pergunta deve ter no maximo {settings.max_tarot_question_length} caracteres.")
    if not any(ch.isalpha() for ch in texto):
        raise erro_http(400, "READING_QUESTION_INVALID_CONTENT", "Pergunta deve conter texto legivel.")
    return texto


def extrair_simbolo(nome_carta: str) -> str:
    mapa = {
        "Lua": "&#9790;", "Sol": "&#9728;", "Estrela": "&#11088;",
        "Mago": "&#128295;", "Louco": "&#9854;", "Morte": "&#9760;",
        "Torre": "&#128303;", "Carro": "&#9855;", "Forca": "&#8982;",
        "Eremita": "&#128302;", "Justica": "&#9878;", "Diabo": "&#9760;",
        "Mundo": "&#127758;", "Julgamento": "&#9733;", "Roda": "&#9855;",
        "Enamorados": "&#9829;", "Sacerdotisa": "&#128274;",
        "Imperatriz": "&#9775;", "Imperador": "&#9732;",
        "Hierofante": "&#9768;", "Enforcado": "&#9835;", "Temperanca": "&#9763;",
    }
    for key, value in mapa.items():
        if key.lower() in (nome_carta or "").lower():
            return value
    return "&#10022;"


def sortear_cartas(qtd: int) -> list[dict]:
    return sortear(qtd)


def gerar_carta_do_dia(carta: dict) -> str:
    return ai_service.gerar_carta_do_dia(carta)


def gerar_interpretacao(pergunta: str, cartas: list[dict]) -> str:
    return reading_service.gerar_interpretacao_tres_cartas(pergunta, cartas)


def gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
