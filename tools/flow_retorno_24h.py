"""
Processador agendado de automacoes WhatsApp/email.

Mantem o nome antigo porque `scheduler_retorno.bat` e o Task Scheduler ja apontam
para este arquivo.
"""

import sys
from datetime import datetime, timezone

import automation_engine


def processar_retornos():
    print("\n" + "=" * 55)
    print("  MADAME DO LUAR - AUTOMACOES WHATSAPP/EMAIL")
    print("=" * 55)
    print(f"Inicio: {datetime.now(timezone.utc).isoformat()}")
    dry_run = "--dry-run" in sys.argv
    if "--sync-rules" in sys.argv:
        regras = automation_engine.sincronizar_regras_padrao()
        print(f"Regras sincronizadas: {regras}")
    resultado = automation_engine.processar_pendentes(dry_run=dry_run)
    if dry_run:
        print("Modo dry-run: nenhum email/WhatsApp foi enviado e nenhum status foi alterado.")
    print(
        "Processados: {processados} | Enviados: {enviados} | Falhas: {falhas}".format(
            **resultado
        )
    )
    for item in resultado["eventos"]:
        print(f"  - {item['message_id']} -> {item['status']}")
    print("=" * 55 + "\n")
    return resultado


def criar_evento_teste():
    user = {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "nome": "Viajante Teste",
        "email": "teste@madame.com.br",
    }
    print(automation_engine.agendar_boas_vindas(user))


if __name__ == "__main__":
    if "--criar-teste" in sys.argv:
        criar_evento_teste()
    else:
        processar_retornos()
