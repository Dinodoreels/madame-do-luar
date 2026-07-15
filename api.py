"""Bootstrap de compatibilidade da API Madame do Luar.

O backend historico foi movido para `app.legacy_api` durante a Fase 4.
Este arquivo deve continuar pequeno para preservar comandos antigos como:

    uvicorn api:app --host 0.0.0.0 --port 8000

Novos ambientes podem usar:

    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from app.legacy_api import app


__all__ = ["app"]
