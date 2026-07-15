from typing import Optional

from pydantic import BaseModel


class AuthRequestModel(BaseModel):
    class Config:
        extra = "forbid"


class RegistrarRequest(AuthRequestModel):
    nome: str
    email: str
    senha: str
    whatsapp: Optional[str] = None
    avatar_url: Optional[str] = None
    whatsapp_opt_in: Optional[bool] = False
    email_opt_in: Optional[bool] = False
    terms_accepted: bool = False
    privacy_accepted: bool = False
    ai_notice_accepted: bool = False


class LoginRequest(AuthRequestModel):
    email: str
    senha: str


class ForgotPasswordRequest(AuthRequestModel):
    email: str


class ResetPasswordRequest(AuthRequestModel):
    token: str
    nova_senha: str
