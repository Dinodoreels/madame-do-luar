import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from dotenv import load_dotenv


load_dotenv()

SIMULATED_WHATSAPP_RESPONSE = {
    "provider": "simulation",
    "status": "simulated",
    "message": "Credenciais WhatsApp ausentes; envio simulado.",
}


def _app_env() -> str:
    return os.getenv("APP_ENV", "development").strip().lower()


def simulacao_notificacoes_permitida() -> bool:
    if _app_env() in {"production", "staging"}:
        return os.getenv("ALLOW_SIMULATED_NOTIFICATIONS", "false").strip().lower() == "true"
    return os.getenv("ALLOW_SIMULATED_NOTIFICATIONS", "true").strip().lower() == "true"


def destinatario_email(email: str) -> str:
    """Aplica override operacional para centralizar emails do sistema quando configurado."""
    return os.getenv("EMAIL_DEFAULT_RECIPIENT", "").strip() or (email or "").strip()


def enviar_email(destinatario: str, assunto: str, corpo: str) -> bool:
    """Envia e-mail via SMTP. Retorna True se enviado ou simulado de forma explicita."""
    destinatario_final = destinatario_email(destinatario)
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT") or 587)
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if not destinatario_final:
        print("[EMAIL] Destinatario ausente.")
        return False

    if not smtp_user or not smtp_pass:
        if not simulacao_notificacoes_permitida():
            print("[EMAIL] Credenciais SMTP ausentes e simulacao desabilitada.")
            return False
        print("[EMAIL] Credenciais SMTP ausentes no .env. Simulando envio...")
        print(f"  Para: {destinatario_final}\n  Assunto: {assunto}\n  Corpo: {corpo[:80]}...")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = smtp_user
        msg["To"] = destinatario_final
        msg.attach(MIMEText(corpo, "plain", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, destinatario_final, msg.as_string())

        print(f"[EMAIL] Enviado com sucesso para {destinatario_final}.")
        return True
    except Exception as exc:
        print(f"[EMAIL] Falha ao enviar: {exc}")
        return False


def normalizar_whatsapp(numero: str) -> str:
    """Normaliza telefone para formato internacional sem sinais. Ex: 5511999999999."""
    digits = re.sub(r"\D", "", numero or "")
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) in (10, 11):
        digits = "55" + digits
    return digits


def destinatario_whatsapp(numero: str) -> str:
    """Aplica override operacional para centralizar mensagens do sistema quando configurado."""
    override = os.getenv("WHATSAPP_DEFAULT_RECIPIENT", "").strip()
    return normalizar_whatsapp(override or numero)


def whatsapp_configurado() -> bool:
    provider = os.getenv("WHATSAPP_PROVIDER", "uazapi").strip().lower()
    api_url = os.getenv("WHATSAPP_API_URL")
    api_token = os.getenv("WHATSAPP_API_TOKEN")
    if provider == "evolution":
        return bool(api_url and api_token and os.getenv("WHATSAPP_INSTANCE_NAME"))
    if provider == "uazapi":
        return bool(api_url and api_token)
    return bool(api_url and api_token)


def _uazapi_endpoint(api_url: str) -> str:
    base = api_url.rstrip("/")
    if base.endswith("/send/text"):
        return base
    return f"{base}/send/text"


def _uazapi_health_endpoint(api_url: str) -> str:
    base = api_url.rstrip("/")
    if "/send/" in base:
        base = base.split("/send/", 1)[0]
    return f"{base}/instance/wa_messages_limits"


def _evolution_endpoint(api_url: str) -> str:
    instance = os.getenv("WHATSAPP_INSTANCE_NAME", "").strip()
    base = api_url.rstrip("/")
    if instance and base.endswith(f"/message/sendText/{instance}"):
        return base
    return f"{base}/message/sendText/{instance}"


def _evolution_health_endpoint(api_url: str) -> str:
    instance = os.getenv("WHATSAPP_INSTANCE_NAME", "").strip()
    base = api_url.rstrip("/")
    if instance and base.endswith(f"/message/sendText/{instance}"):
        base = base[: -len(f"/message/sendText/{instance}")]
    return f"{base}/instance/connectionState/{instance}"


def whatsapp_diagnostico_config() -> dict:
    provider = os.getenv("WHATSAPP_PROVIDER", "uazapi").strip().lower()
    api_url = os.getenv("WHATSAPP_API_URL", "").strip()
    api_token = os.getenv("WHATSAPP_API_TOKEN", "").strip()
    instance = os.getenv("WHATSAPP_INSTANCE_NAME", "").strip()
    required_missing = []
    if not api_url:
        required_missing.append("WHATSAPP_API_URL")
    if not api_token:
        required_missing.append("WHATSAPP_API_TOKEN")
    if provider == "evolution" and not instance:
        required_missing.append("WHATSAPP_INSTANCE_NAME")

    send_endpoint = ""
    health_endpoint = ""
    if api_url:
        if provider == "uazapi":
            send_endpoint = _uazapi_endpoint(api_url)
            health_endpoint = _uazapi_health_endpoint(api_url)
        elif provider == "evolution":
            send_endpoint = _evolution_endpoint(api_url)
            health_endpoint = _evolution_health_endpoint(api_url)

    return {
        "provider": provider,
        "configured": not required_missing and provider in {"uazapi", "evolution"},
        "supported": provider in {"uazapi", "evolution"},
        "required_missing": required_missing,
        "send_endpoint": send_endpoint,
        "health_endpoint": health_endpoint,
        "simulation_allowed": simulacao_notificacoes_permitida(),
    }


def validar_whatsapp_status() -> dict:
    """Executa prova nao destrutiva do provedor WhatsApp configurado."""
    diag = whatsapp_diagnostico_config()
    provider = diag["provider"]
    if not diag["supported"]:
        return {**diag, "ok": False, "status": "unsupported_provider", "error": f"Provedor nao suportado: {provider}"}
    if not diag["configured"]:
        return {**diag, "ok": False, "status": "missing_config", "error": "Configuracao incompleta."}

    headers = {"Content-Type": "application/json"}
    if provider == "uazapi":
        headers["token"] = os.getenv("WHATSAPP_API_TOKEN", "").strip()
        if os.getenv("UAZAPI_CONVERT", "true").lower() == "true":
            headers["convert"] = "true"
    elif provider == "evolution":
        headers["apikey"] = os.getenv("WHATSAPP_API_TOKEN", "").strip()

    try:
        response = requests.get(diag["health_endpoint"], headers=headers, timeout=10)
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text[:300]}

        ok = response.status_code in (200, 201)
        return {
            **diag,
            "ok": ok,
            "status": "ok" if ok else "provider_error",
            "http_status": response.status_code,
            "provider_response": payload,
            "error": None if ok else f"HTTP {response.status_code}",
        }
    except Exception as exc:
        return {**diag, "ok": False, "status": "request_failed", "error": str(exc)[:220]}


def _send_evolution(numero: str, mensagem: str) -> dict:
    api_url = os.getenv("WHATSAPP_API_URL", "").strip()
    api_token = os.getenv("WHATSAPP_API_TOKEN", "").strip()
    numero_normalizado = destinatario_whatsapp(numero)

    if not numero_normalizado:
        return {
            "ok": False,
            "status": "failed",
            "recipient": numero,
            "error": "Numero de WhatsApp ausente ou invalido.",
            "provider": "evolution",
            "provider_response": {},
        }

    if not whatsapp_configurado():
        if not simulacao_notificacoes_permitida():
            return {
                "ok": False,
                "status": "failed",
                "recipient": numero_normalizado,
                "error": "Credenciais WhatsApp ausentes e simulacao desabilitada.",
                "provider": "evolution",
                "provider_response": {},
            }
        print("[WHATSAPP] Credenciais ausentes no .env. Simulando envio...")
        print(f"  Para: {numero_normalizado}\n  Mensagem: {mensagem[:80]}...")
        return {
            "ok": True,
            "status": "simulated",
            "recipient": numero_normalizado,
            "provider": "evolution",
            "provider_response": SIMULATED_WHATSAPP_RESPONSE,
        }

    headers = {"apikey": api_token, "Content-Type": "application/json"}
    payload = {
        "number": numero_normalizado,
        "text": mensagem,
        "delay": int(os.getenv("WHATSAPP_SEND_DELAY_MS", "1200")),
        "linkPreview": os.getenv("WHATSAPP_LINK_PREVIEW", "true").lower() == "true",
    }
    try:
        response = requests.post(_evolution_endpoint(api_url), headers=headers, json=payload, timeout=20)
        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text}

        ok = response.status_code in (200, 201)
        if ok:
            print(f"[WHATSAPP] Enviado com sucesso para {numero_normalizado}.")
            return {
                "ok": True,
                "status": "sent",
                "recipient": numero_normalizado,
                "provider": "evolution",
                "provider_response": data,
            }

        print(f"[WHATSAPP] Resposta inesperada: {response.status_code} - {response.text}")
        return {
            "ok": False,
            "status": "failed",
            "recipient": numero_normalizado,
            "error": f"Evolution API HTTP {response.status_code}",
            "provider": "evolution",
            "provider_response": data,
        }
    except Exception as exc:
        print(f"[WHATSAPP] Falha ao enviar: {exc}")
        return {
            "ok": False,
            "status": "failed",
            "recipient": numero_normalizado,
            "error": str(exc),
            "provider": "evolution",
            "provider_response": {},
        }


def _send_uazapi(numero: str, mensagem: str) -> dict:
    api_url = os.getenv("WHATSAPP_API_URL", "").strip()
    api_token = os.getenv("WHATSAPP_API_TOKEN", "").strip()
    numero_normalizado = destinatario_whatsapp(numero)

    if not numero_normalizado:
        return {
            "ok": False,
            "status": "failed",
            "recipient": numero,
            "error": "Numero de WhatsApp ausente ou invalido.",
            "provider": "uazapi",
            "provider_response": {},
        }

    if not whatsapp_configurado():
        if not simulacao_notificacoes_permitida():
            return {
                "ok": False,
                "status": "failed",
                "recipient": numero_normalizado,
                "error": "Credenciais WhatsApp ausentes e simulacao desabilitada.",
                "provider": "uazapi",
                "provider_response": {},
            }
        print("[WHATSAPP] Credenciais Uazapi ausentes no .env. Simulando envio...")
        print(f"  Para: {numero_normalizado}\n  Mensagem: {mensagem[:80]}...")
        return {
            "ok": True,
            "status": "simulated",
            "recipient": numero_normalizado,
            "provider": "uazapi",
            "provider_response": SIMULATED_WHATSAPP_RESPONSE,
        }

    headers = {
        "token": api_token,
        "Content-Type": "application/json",
    }
    if os.getenv("UAZAPI_CONVERT", "true").lower() == "true":
        headers["convert"] = "true"

    payload = {
        "number": numero_normalizado,
        "text": mensagem,
    }

    try:
        response = requests.post(_uazapi_endpoint(api_url), headers=headers, json=payload, timeout=20)
        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text}

        ok = response.status_code in (200, 201)
        if ok:
            print(f"[WHATSAPP] Uazapi enviou com sucesso para {numero_normalizado}.")
            return {
                "ok": True,
                "status": "sent",
                "recipient": numero_normalizado,
                "provider": "uazapi",
                "provider_response": data,
            }

        print(f"[WHATSAPP] Uazapi respondeu {response.status_code}: {response.text}")
        return {
            "ok": False,
            "status": "failed",
            "recipient": numero_normalizado,
            "error": f"Uazapi HTTP {response.status_code}",
            "provider": "uazapi",
            "provider_response": data,
        }
    except Exception as exc:
        print(f"[WHATSAPP] Falha ao enviar via Uazapi: {exc}")
        return {
            "ok": False,
            "status": "failed",
            "recipient": numero_normalizado,
            "error": str(exc),
            "provider": "uazapi",
            "provider_response": {},
        }


def enviar_whatsapp_result(numero: str, mensagem: str) -> dict:
    """Envia WhatsApp e retorna status estruturado para log/auditoria."""
    provider = os.getenv("WHATSAPP_PROVIDER", "uazapi").strip().lower()
    if provider == "uazapi":
        return _send_uazapi(numero, mensagem)
    if provider == "evolution":
        return _send_evolution(numero, mensagem)
    return {
        "ok": False,
        "status": "failed",
        "recipient": destinatario_whatsapp(numero),
        "error": f"Provedor WhatsApp nao suportado neste adaptador: {provider}",
        "provider": provider,
        "provider_response": {},
    }


def enviar_whatsapp(numero: str, mensagem: str) -> bool:
    """Envia mensagem via WhatsApp. Retorna True se enviado ou simulado explicitamente."""
    return bool(enviar_whatsapp_result(numero, mensagem).get("ok"))
