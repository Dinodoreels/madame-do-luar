import db_client

from app.shared.repository import audit_event, log_event


class AuthRepository:
    def create_user(self, **payload):
        return db_client.criar_usuario(**payload)

    def verify_login(self, email: str, password: str):
        return db_client.verificar_login(email, password)

    def create_password_reset_token(self, email: str):
        return db_client.criar_token_recuperacao(email)

    def reset_password_by_token(self, token: str, password: str):
        return db_client.redefinir_senha_por_token(token, password)

    def log(self, *args, **kwargs):
        return log_event(*args, **kwargs)

    def audit(self, *args, **kwargs):
        return audit_event(*args, **kwargs)
