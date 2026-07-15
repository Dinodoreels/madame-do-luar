import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _csv_env(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_env: str
    cors_origins: Tuple[str, ...]
    jwt_secret: str
    jwt_issuer: str
    jwt_expires_seconds: int
    rate_limit_window_seconds: int
    rate_limit_max_requests: int
    max_tarot_question_length: int
    min_tarot_question_length: int
    auth_cookie_name: str
    auth_cookie_secure: bool
    auth_cookie_samesite: str
    log_level: str
    frontend_dir: Path
    media_dir: Path
    video_dir: Path


def load_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    cors_default = (
        "null,http://localhost:8000,http://127.0.0.1:8000,"
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5500,http://127.0.0.1:5500"
    )
    cors_origins = tuple(_csv_env("APP_CORS_ORIGINS", cors_default))
    if app_env == "production":
        unsafe_origins = [
            origin
            for origin in cors_origins
            if origin in {"*", "null"} or "localhost" in origin or "127.0.0.1" in origin
        ]
        if not cors_origins or unsafe_origins:
            raise RuntimeError("APP_CORS_ORIGINS de producao deve listar apenas dominios HTTPS reais.")

    jwt_secret = os.getenv("JWT_SECRET", "")
    if not jwt_secret or len(jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET obrigatorio no .env com pelo menos 32 caracteres.")

    media_dir = ROOT_DIR / "imagems"
    return Settings(
        app_env=app_env,
        cors_origins=cors_origins,
        jwt_secret=jwt_secret,
        jwt_issuer=os.getenv("JWT_ISSUER", "madame-do-luar"),
        jwt_expires_seconds=int(os.getenv("JWT_EXPIRES_SECONDS", "86400")),
        rate_limit_window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
        rate_limit_max_requests=int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "120")),
        max_tarot_question_length=int(os.getenv("MAX_TAROT_QUESTION_LENGTH", "600")),
        min_tarot_question_length=int(os.getenv("MIN_TAROT_QUESTION_LENGTH", "3")),
        auth_cookie_name="mdl_access_token",
        auth_cookie_secure=app_env == "production",
        auth_cookie_samesite="lax",
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        frontend_dir=ROOT_DIR / "frontend",
        media_dir=media_dir,
        video_dir=media_dir / "VIDEO hero",
    )


settings = load_settings()
