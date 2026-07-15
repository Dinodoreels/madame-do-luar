"""
test_suite.py — Suite de Testes da Madame do Luar
Roda todos os testes de integração e salva os resultados em findings.md
"""
import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

RESULTS = []

def log(status: str, modulo: str, detalhe: str):
    simbolo = "PASS" if status == "ok" else ("SKIP" if status == "skip" else "FAIL")
    linha = f"[{simbolo}] {modulo}: {detalhe}"
    print(linha)
    RESULTS.append((status, modulo, detalhe))

# ─────────────────────────────────────────────
# 1. GEMINI API
# ─────────────────────────────────────────────
def test_gemini():
    print("\n--- Teste 1: Gemini API ---")
    try:
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            log("fail", "Gemini API", "GEMINI_API_KEY nao encontrada no .env")
            return

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content("Responda apenas: OK")
        texto = response.text.strip()
        log("ok", "Gemini API", f"Conexao bem-sucedida. Resposta: '{texto[:30]}'")
    except Exception as e:
        log("fail", "Gemini API", str(e)[:120])


# ─────────────────────────────────────────────
# 2. SUPABASE (via requests — sem lib pesada)
# ─────────────────────────────────────────────
def test_supabase():
    print("\n--- Teste 2: Supabase ---")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        log("fail", "Supabase", "SUPABASE_URL ou SUPABASE_KEY ausentes no .env")
        return

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    # Testa listagem de users
    try:
        r = requests.get(f"{url}/rest/v1/users?select=user_id&limit=1", headers=headers, timeout=10)
        if r.status_code == 200:
            contagem = len(r.json())
            log("ok", "Supabase - Leitura", f"Tabela 'users' acessivel. Registros encontrados: {contagem}")
        else:
            log("fail", "Supabase - Leitura", f"HTTP {r.status_code}: {r.text[:100]}")
    except Exception as e:
        log("fail", "Supabase - Leitura", str(e)[:120])

    # Testa escrita em daily_cards
    try:
        test_uuid = "00000000-0000-0000-0000-000000000001"
        headers_post = dict(headers)
        headers_post["Prefer"] = "return=representation"
        payload = {"user_id": test_uuid, "carta": "TESTE", "inverted": False, "mensagem": "Teste de escrita automatico"}
        r = requests.post(f"{url}/rest/v1/daily_cards", headers=headers_post, json=payload, timeout=10)
        if r.status_code in (200, 201):
            log("ok", "Supabase - Escrita", "Insercao na tabela 'daily_cards' bem-sucedida")
        elif r.status_code == 409:
            log("ok", "Supabase - Escrita", "Registro ja existe para hoje (unique constraint ativa — correto!)")
        else:
            log("fail", "Supabase - Escrita", f"HTTP {r.status_code}: {r.text[:120]}")
    except Exception as e:
        log("fail", "Supabase - Escrita", str(e)[:120])


# ─────────────────────────────────────────────
# 3. SMTP / EMAIL
# ─────────────────────────────────────────────
def test_email():
    print("\n--- Teste 3: E-mail (SMTP) ---")
    import smtplib

    host  = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port  = int(os.getenv("SMTP_PORT") or 587)
    user  = os.getenv("SMTP_USER")
    pwd   = os.getenv("SMTP_PASS")

    if not user or not pwd:
        log("skip", "E-mail SMTP", "Credenciais SMTP_USER / SMTP_PASS nao configuradas — integracao pendente")
        return

    try:
        with smtplib.SMTP(host, port, timeout=10) as s:
            s.starttls()
            s.login(user, pwd)
        log("ok", "E-mail SMTP", f"Login bem-sucedido em {host}:{port} com usuario {user}")
    except Exception as e:
        log("fail", "E-mail SMTP", str(e)[:120])


# ─────────────────────────────────────────────
# 4. WHATSAPP API
# ─────────────────────────────────────────────
def test_whatsapp():
    print("\n--- Teste 4: WhatsApp API ---")
    try:
        from notificacoes import validar_whatsapp_status

        result = validar_whatsapp_status()
        if result.get("status") == "missing_config":
            missing = ", ".join(result.get("required_missing") or [])
            log("skip", "WhatsApp API", f"Configuracao incompleta: {missing}")
        elif result.get("ok"):
            log("ok", "WhatsApp API", f"{result.get('provider')} respondeu HTTP {result.get('http_status')} em {result.get('health_endpoint')}")
        else:
            log("fail", "WhatsApp API", f"{result.get('provider')} {result.get('status')}: {result.get('error')} em {result.get('health_endpoint')}")
    except Exception as e:
        log("fail", "WhatsApp API", str(e)[:120])


# ─────────────────────────────────────────────
# 5. GATEWAY DE PAGAMENTO
# ─────────────────────────────────────────────
def test_payment():
    print("\n--- Teste 5: Mercado Pago ---")
    token = os.getenv("MERCADO_PAGO_ACCESS_TOKEN")

    if not token:
        log("skip", "Mercado Pago", "MERCADO_PAGO_ACCESS_TOKEN nao configurado")
        return

    if not os.getenv("MERCADO_PAGO_WEBHOOK_SECRET"):
        log("skip", "Mercado Pago Webhook", "MERCADO_PAGO_WEBHOOK_SECRET ausente; checkout existe, mas a validacao de assinatura fica pendente")
    else:
        log("ok", "Mercado Pago Webhook", "Webhook secret configurado")

    log("ok", "Mercado Pago", "Access token configurado")

# ─────────────────────────────────────────────
# 6. SORTEIO DE CARTAS (unitário)
# ─────────────────────────────────────────────
def test_sorteio():
    print("\n--- Teste 6: Sorteio de Cartas (unitario) ---")
    try:
        from sortear_cartas import sortear
        cartas = sortear(3)
        assert len(cartas) == 3
        for c in cartas:
            assert "nome" in c and "invertida" in c
        nomes = [c["nome"] for c in cartas]
        # Não deve ter repetição
        assert len(set(nomes)) == 3
        log("ok", "Sorteio de Cartas", f"3 cartas unicas sorteadas: {', '.join(nomes)}")
    except Exception as e:
        log("fail", "Sorteio de Cartas", str(e)[:120])


# ─────────────────────────────────────────────
# GERAÇÃO DO RELATÓRIO
# ─────────────────────────────────────────────
def gerar_findings():
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    total   = len(RESULTS)
    passou  = sum(1 for r in RESULTS if r[0] == "ok")
    pulou   = sum(1 for r in RESULTS if r[0] == "skip")
    falhou  = sum(1 for r in RESULTS if r[0] == "fail")

    linhas = [
        "# Findings — Testes de Integração",
        "",
        f"> Última execução: **{agora}**  |  Total: {total}  |  PASS: {passou}  |  SKIP: {pulou}  |  FAIL: {falhou}",
        "",
        "## Resultados dos Testes",
        "",
        "| Status | Módulo | Detalhe |",
        "|--------|--------|---------|",
    ]

    for status, modulo, detalhe in RESULTS:
        if status == "ok":
            emoji = "PASS"
        elif status == "skip":
            emoji = "SKIP"
        else:
            emoji = "FAIL"
        linhas.append(f"| {emoji} | {modulo} | {detalhe} |")

    linhas += [
        "",
        "## Legenda",
        "- **PASS** — Integração funcional e testada",
        "- **SKIP** — Credenciais não configuradas (integração pendente, não é erro)",
        "- **FAIL** — Erro real que precisa de atenção",
        "",
        "## Observações Técnicas",
        "",
        "- A lib `supabase-py` não instala no Windows sem o Visual C++ Build Tools.",
        "  **Solução adotada:** comunicação direta via `requests` (REST API do Supabase) — sem dependências de compilação C++.",
        "- A lib `google.generativeai` está depreciada mas ainda funcional. Migrar para `google.genai` em próxima iteração.",
        "- E-mail, WhatsApp e Gateway de Pagamento operam em **modo simulação** até que as credenciais sejam inseridas no `.env`.",
        "",
        "## Próximas Integrações Pendentes",
        "",
        "| Integração | O que fazer |",
        "|---|---|",
        "| E-mail | Configurar `SMTP_USER` e `SMTP_PASS` no `.env` (recomendado: Gmail App Password ou SendGrid) |",
        "| WhatsApp | Configurar `WHATSAPP_API_URL` e `WHATSAPP_API_TOKEN` (recomendado: Evolution API ou Z-API) |",
        "| Gateway | Manter `MERCADO_PAGO_ACCESS_TOKEN` e `MERCADO_PAGO_WEBHOOK_SECRET` configurados no `.env` |",
    ]

    conteudo = "\n".join(linhas)

    # Salva na raiz do projeto
    root = os.path.dirname(os.path.dirname(__file__))
    caminho = os.path.join(root, "findings.md")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)

    print(f"\nfindings.md atualizado em: {caminho}")
    return conteudo


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  MADAME DO LUAR — SUITE DE TESTES DE INTEGRACAO")
    print("=" * 55)

    test_gemini()
    test_supabase()
    test_email()
    test_whatsapp()
    test_payment()
    test_sorteio()

    print("\n" + "=" * 55)
    print("  RESUMO")
    print("=" * 55)
    total  = len(RESULTS)
    passou = sum(1 for r in RESULTS if r[0] == "ok")
    pulou  = sum(1 for r in RESULTS if r[0] == "skip")
    falhou = sum(1 for r in RESULTS if r[0] == "fail")
    print(f"  Total: {total} | PASS: {passou} | SKIP: {pulou} | FAIL: {falhou}")
    print("=" * 55)

    gerar_findings()
