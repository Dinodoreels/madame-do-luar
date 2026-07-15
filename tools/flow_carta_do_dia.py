import json
from sortear_cartas import sortear
from llm_client import chamar_madame_do_luar
import db_client

def executar_carta_do_dia(user_id):
    """
    Fluxo que reflete exatamente o POP `architecture/carta_do_dia.md`
    """
    # 1. Verificação de elegibilidade no Supabase
    print(f"Verificando se o usuario '{user_id}' ja tirou a carta hoje...")
    if db_client.has_daily_card_today(user_id):
        return "Você já sorteou sua carta hoje. As energias pedem que você reflita sobre ela antes de puxar uma nova. Volte amanhã!"
    
    # 2. Seleção de Carta
    print("Sorteando a carta...")
    carta = sortear(1)[0]
    
    # 3. Montagem do Payload
    payload = {
        "carta": carta["nome"],
        "invertida": "true" if carta["invertida"] else "false"
    }
    print(f"Carta sorteada: {payload['carta']} {'(Invertida)' if carta['invertida'] else '(Normal)'}")
    
    # 4. Chamada da IA
    print("Madame do Luar esta canalizando as energias (chamando API Gemini)...")
    try:
        resposta = chamar_madame_do_luar(
            prompt_base_path="prompts/carta_do_dia.md",
            carta=payload["carta"],
            invertida=payload["invertida"]
        )
    except Exception as e:
        return f"Erro ao contactar a IA: {e}"
        
    # 5. Persistência real no Supabase
    print("Salvando leitura na tabela `daily_cards`...")
    db_client.insert_daily_card(user_id, carta["nome"], carta["invertida"], resposta)
    
    # 6. Resposta ao usuário
    return resposta

if __name__ == "__main__":
    # Teste de execução no terminal
    import sys
    print("\n" + "="*50)
    print("   INICIANDO FLUXO - CARTA DO DIA")
    print("="*50 + "\n")
    
    # Prepara o usuário de teste com um UUID válido
    test_uuid = "00000000-0000-0000-0000-000000000001"
    url, headers = db_client.get_supabase_headers()
    import requests
    # Insere ou ignora erro se já existir o usuário
    requests.post(f"{url}/rest/v1/users", headers=headers, json={"user_id": test_uuid, "nome": "Viajante Teste"})
    
    resultado = executar_carta_do_dia(test_uuid)
    
    print("\n" + "="*50)
    print("   RESPOSTA DA MADAME DO LUAR")
    print("="*50 + "\n")
    print(resultado)
    print("\n" + "="*50 + "\n")
