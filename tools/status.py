"""
status.py — Painel de Status da Madame do Luar
Mostra um resumo de tudo que está acontecendo no sistema.
Rode com: python tools/status.py
"""
import os
import sys
import requests
from datetime import datetime, timezone, date
from dotenv import load_dotenv

load_dotenv()

SEP = "=" * 58

def get_db():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None, None
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    return url, headers

def fmt_linha(label, valor, largura=30):
    return f"  {label:<{largura}} {valor}"

def painel():
    print()
    print(SEP)
    print("  MADAME DO LUAR — PAINEL DE STATUS")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(SEP)

    url, headers = get_db()

    if not url:
        print("  ERRO: Credenciais do Supabase nao encontradas.")
        return

    # ── Usuarios ──
    print("\n  [ USUARIOS ]")
    r = requests.get(f"{url}/rest/v1/users?select=user_id,nome,assinante,criado_em", headers=headers)
    usuarios = r.json() if isinstance(r.json(), list) else []
    total_usuarios = len(usuarios)
    assinantes = sum(1 for u in usuarios if u.get("assinante"))
    print(fmt_linha("Total cadastrados:", total_usuarios))
    print(fmt_linha("Assinantes ativos:", assinantes))
    print(fmt_linha("Gratuitos:", total_usuarios - assinantes))

    # ── Cartas do Dia ──
    print("\n  [ CARTAS DO DIA ]")
    hoje = str(date.today())
    r = requests.get(f"{url}/rest/v1/daily_cards?select=daily_id,carta,criado_em", headers=headers)
    all_daily = r.json() if isinstance(r.json(), list) else []
    hoje_daily = [d for d in all_daily if d.get("criado_em") == hoje]
    print(fmt_linha("Total historico:", len(all_daily)))
    print(fmt_linha("Enviadas hoje:", len(hoje_daily)))

    # ── Leituras ──
    print("\n  [ LEITURAS DE 3 CARTAS ]")
    r = requests.get(f"{url}/rest/v1/readings?select=reading_id,criado_em", headers=headers)
    readings = r.json() if isinstance(r.json(), list) else []
    print(fmt_linha("Total de leituras:", len(readings)))

    # ── Perguntas ──
    r = requests.get(f"{url}/rest/v1/questions?select=question_id,tema", headers=headers)
    questions = r.json() if isinstance(r.json(), list) else []
    print(fmt_linha("Total de perguntas:", len(questions)))

    # ── Mensagens / Retornos ──
    print("\n  [ MENSAGENS AUTOMATICAS ]")
    r = requests.get(f"{url}/rest/v1/message_events?select=message_id,tipo,status,canal", headers=headers)
    eventos = r.json() if isinstance(r.json(), list) else []
    pending = [e for e in eventos if e.get("status") == "pending"]
    sent    = [e for e in eventos if e.get("status") == "sent"]
    failed  = [e for e in eventos if e.get("status") == "failed"]
    print(fmt_linha("Total de eventos:", len(eventos)))
    print(fmt_linha("Pendentes:", len(pending)))
    print(fmt_linha("Enviados:", len(sent)))
    print(fmt_linha("Falhas:", len(failed)))

    # ── Ambiente ──
    print("\n  [ AMBIENTE / INTEGRACOES ]")
    checks = [
        ("Gemini API",       bool(os.getenv("GEMINI_API_KEY"))),
        ("Supabase",         bool(os.getenv("SUPABASE_URL"))),
        ("E-mail SMTP",      bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"))),
        ("WhatsApp API",     bool(os.getenv("WHATSAPP_API_URL"))),
        ("Mercado Pago", bool(os.getenv("MERCADO_PAGO_ACCESS_TOKEN"))),
    ]
    for nome, ok in checks:
        status_txt = "ATIVO" if ok else "PENDENTE"
        print(fmt_linha(nome + ":", status_txt))

    # ── Logs recentes ──
    print("\n  [ LOGS RECENTES ]")
    tmp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".tmp")
    if os.path.isdir(tmp_dir):
        logs = sorted([f for f in os.listdir(tmp_dir) if f.endswith(".log")], reverse=True)
        if logs:
            for log in logs[:3]:
                log_path = os.path.join(tmp_dir, log)
                size = os.path.getsize(log_path)
                print(fmt_linha(log, f"{size} bytes"))
        else:
            print("  Nenhum log encontrado em .tmp/")
    else:
        print("  Pasta .tmp/ nao encontrada.")

    print()
    print(SEP)
    print()

if __name__ == "__main__":
    painel()
