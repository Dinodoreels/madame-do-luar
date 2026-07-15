import argparse
import json
import os
import sys

from dotenv import load_dotenv

import db_client
from notificacoes import enviar_whatsapp_result, normalizar_whatsapp, whatsapp_configurado


load_dotenv()


def _register_log(number: str, message: str, result: dict) -> None:
    provider = result.get("provider") or os.getenv("WHATSAPP_PROVIDER", "uazapi")
    payload = {
        "channel": "whatsapp",
        "type": "manual_test",
        "recipient": normalizar_whatsapp(number),
        "subject": f"Teste WhatsApp {provider}",
        "status": result.get("status") or ("sent" if result.get("ok") else "failed"),
        "error_message": result.get("error"),
        "provider_response": result.get("provider_response") or {},
        "metadata": {
            "provider": provider,
            "message_preview": message[:120],
            "configured": whatsapp_configurado(),
        },
    }
    created = db_client.criar_registro("notification_logs", payload)
    if isinstance(created, dict) and created.get("erro"):
        print("WARN notification_logs nao recebeu o registro: " + str(created["erro"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Envia teste real/simulado via provedor WhatsApp configurado.")
    parser.add_argument("--number", default=os.getenv("WHATSAPP_TEST_NUMBER", ""), help="Numero com DDI. Ex: 5511999999999")
    parser.add_argument(
        "--message",
        default="Teste Madame do Luar: WhatsApp configurado com sucesso.",
        help="Mensagem de teste.",
    )
    args = parser.parse_args()

    if not args.number:
        print("FAIL informe --number ou WHATSAPP_TEST_NUMBER no .env")
        return 1

    result = enviar_whatsapp_result(args.number, args.message)
    _register_log(args.number, args.message, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
