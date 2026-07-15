from typing import Optional

from pydantic import BaseModel


class UsersRequestModel(BaseModel):
    class Config:
        extra = "forbid"


class PerfilUpdateRequest(UsersRequestModel):
    nome: Optional[str] = None
    whatsapp: Optional[str] = None
    avatar_url: Optional[str] = None
    whatsapp_opt_in: Optional[bool] = None
    email_opt_in: Optional[bool] = None


class SenhaUpdateRequest(UsersRequestModel):
    senha_atual: str
    nova_senha: str


class AccountDeleteRequest(UsersRequestModel):
    confirmation: str
    reason: Optional[str] = None
