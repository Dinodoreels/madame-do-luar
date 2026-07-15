import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
import db_client
from notificacoes import enviar_whatsapp, enviar_email

load_dotenv()

# Réguas de cobrança e avisos
REGUA_COBRANCA = {
    -3: {
        "tipo": "aviso_previo",
        "assunto": "A Lua avisa: Seu acesso vai expirar em breve ✨",
        "msg": "Filho(a) da Lua, seu acesso ao Madame do Luar expira em 3 dias. Não deixe que as estrelas se apaguem no seu caminho. Renove agora para continuar recebendo suas orientações diárias."
    },
    0: {
        "tipo": "expiracao",
        "assunto": "Seu acesso expirou hoje 🌙",
        "msg": "O ciclo se encerrou hoje. Seu acesso ao Madame do Luar foi pausado, mas as cartas ainda têm muito a te dizer. Faça a renovação para reabrir os seus caminhos."
    },
    3: {
        "tipo": "recuperacao_3d",
        "assunto": "Sinto sua falta nas tiragens...",
        "msg": "Faz 3 dias que você não consulta as estrelas. O universo tem respostas esperando por você. Renove seu acesso e volte a iluminar suas decisões."
    },
    7: {
        "tipo": "recuperacao_7d",
        "assunto": "Um recado das cartas para você 🃏",
        "msg": "A Roda da Fortuna girou, mas você ficou parado(a). Já faz 7 dias que sua assinatura expirou. Que tal reativar seu acesso e ver o que o destino preparou para esta semana?"
    },
    30: {
        "tipo": "recuperacao_30d",
        "assunto": "Um mês longe da luz... 💫",
        "msg": "Uma lua inteira se passou desde que você nos deixou. Volte para o Madame do Luar, temos novos rituais e leituras profundas aguardando sua energia."
    }
}

def processar_cron_diario():
    """
    Roda diariamente para checar assinaturas expirando ou expiradas.
    Para PIX: cobra renovação manual.
    Para Cartão Recusado (past_due): cobra atualização de cartão.
    """
    print(f"[{datetime.now().isoformat()}] Iniciando Cron de Marketing/Cobrança...")

    url, headers = db_client.get_supabase_headers()
    import requests
    
    # Buscar todas as assinaturas ativas, canceled ou past_due
    r = requests.get(f"{url}/rest/v1/subscriptions?select=*", headers=headers)
    assinaturas = r.json()

    hoje = datetime.now(timezone.utc).date()

    for sub in assinaturas:
        user_id = sub.get("user_id")
        status = sub.get("status")
        renovacao_str = sub.get("renovacao")

        if not renovacao_str or not user_id:
            continue

        try:
            data_renovacao = datetime.fromisoformat(renovacao_str).date()
        except ValueError:
            continue

        # Calcula a diferença em dias. 
        # Se hoje > data_renovacao, diff é positivo (venceu há X dias)
        # Se hoje < data_renovacao, diff é negativo (vencerá em X dias)
        diff_dias = (hoje - data_renovacao).days

        # Pular se não tivermos régua para este dia exato
        if diff_dias not in REGUA_COBRANCA:
            continue

        regra = REGUA_COBRANCA[diff_dias]

        # Só envia se for past_due (cartão recusado) ou se for um plano que requer renovação manual (ex: Pix).
        # No Mercado Pago Checkout Pro, planos funcionam como acesso por periodo.
        # Mas para o escopo do SaaS, se está vencendo, avisamos.
        if status == "active" and diff_dias > 0:
            # Se passou da data e segue active, o acesso local precisa ser revogado.
            # A renovacao recorrente nativa fica para uma fase futura de preapproval.
            # Precisamos revogar o acesso localmente se diff_dias >= 0.
            if diff_dias == 0:
                print(f"[REVOGACAO] Expirando acesso do usuario {user_id}")
                db_client.atualizar_status_assinatura(user_id, "expired")

        # Busca dados do usuário para notificar
        user = db_client.get_user_by_id(user_id)
        if not user:
            continue
        
        email = user.get("email")
        whatsapp = user.get("whatsapp")

        print(f"[CRON] Enviando '{regra['tipo']}' para {user.get('nome')} ({diff_dias} dias)")

        # Busca a última pergunta do usuário para criar gatilho mental
        q_resp = requests.get(f"{url}/rest/v1/questions?user_id=eq.{user_id}&order=criado_em.desc&limit=1", headers=headers)
        gatilho_mental = ""
        if q_resp.status_code == 200 and q_resp.json():
            ultima_pergunta = q_resp.json()[0].get("pergunta", "")
            if ultima_pergunta:
                gatilho_mental = f"\n\n🔮 As cartas ainda guardam segredos sobre o que você perguntou recentemente: \"{ultima_pergunta}\"."

        link_checkout = f"{os.getenv('APP_BASE_URL', 'http://localhost:8000')} (Acesse para renovar)"
        texto_completo = f"{regra['msg']}{gatilho_mental}\n\nLink: {link_checkout}"

        if email:
            enviar_email(email, regra['assunto'], texto_completo)
        
        if whatsapp:
            # Formatar em negrito para WhatsApp
            msg_wpp = f"*{regra['assunto']}*\n\n{regra['msg']}\n\nLink mágico: {link_checkout}"
            enviar_whatsapp(whatsapp, msg_wpp)

    print("Cron finalizado com sucesso.")

if __name__ == "__main__":
    processar_cron_diario()
