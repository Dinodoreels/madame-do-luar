from typing import Optional

from pydantic import BaseModel, Field

from app.core.config import settings


class ReadingsRequestModel(BaseModel):
    class Config:
        extra = "forbid"


class CartaDoDiaRequest(ReadingsRequestModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    nome: Optional[str] = None


class LeituraRequest(ReadingsRequestModel):
    class Config(ReadingsRequestModel.Config):
        extra = "ignore"

    user_id: Optional[str] = None
    pergunta: Optional[str] = Field(None, max_length=settings.max_tarot_question_length)
    question: Optional[str] = Field(None, max_length=settings.max_tarot_question_length)
    mensagem: Optional[str] = Field(None, max_length=settings.max_tarot_question_length)
    tipo: Optional[str] = "tres_cartas"
    tipo_leitura: Optional[str] = None
    reading_type: Optional[str] = None
