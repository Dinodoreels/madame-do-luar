from sortear_cartas import sortear
from llm_client import chamar_madame_do_luar
import db_client

def executar_leitura_3_cartas(user_id, pergunta):
    """
    Fluxo que reflete exatamente o POP `architecture/leitura_tarot.md`
    """
    # 1. Validação de Acesso (Mock de permissão — expandir com check de assinatura)
    print(f"Verificando acesso para o usuario '{user_id}'...")

    # 2. Registro da Pergunta no Supabase
    print(f"Registrando pergunta na tabela `questions`...")
    question_id = db_client.insert_question(user_id, pergunta)
    if not question_id:
        return "Erro: nao foi possivel registrar a pergunta no banco de dados."
    print(f"Pergunta registrada com ID: {question_id}")

    # 3. Sorteio de 3 Cartas
    print("Sorteando as cartas do Passado, Presente e Futuro...")
    cartas = sortear(3)
    c_passado = cartas[0]
    c_presente = cartas[1]
    c_futuro = cartas[2]

    print(f"Passado: {c_passado['nome']} {'(Inv)' if c_passado['invertida'] else '(N)'}")
    print(f"Presente: {c_presente['nome']} {'(Inv)' if c_presente['invertida'] else '(N)'}")
    print(f"Futuro: {c_futuro['nome']} {'(Inv)' if c_futuro['invertida'] else '(N)'}")

    # 4 e 5. Chamada da IA
    print("Madame do Luar esta costurando as linhas do tempo (chamando API Gemini)...")
    try:
        resposta = chamar_madame_do_luar(
            prompt_base_path="prompts/tres_cartas.md",
            pergunta=pergunta,
            carta_passado=c_passado["nome"],
            invertida_passado="true" if c_passado["invertida"] else "false",
            carta_presente=c_presente["nome"],
            invertida_presente="true" if c_presente["invertida"] else "false",
            carta_futuro=c_futuro["nome"],
            invertida_futuro="true" if c_futuro["invertida"] else "false"
        )
    except Exception as e:
        return f"Erro ao contactar a IA: {e}"

    # 6. Persistência real no Supabase
    print("Salvando leitura na tabela `readings`...")
    db_client.insert_reading(
        question_id=question_id,
        cartas={
            "passado":  c_passado,
            "presente": c_presente,
            "futuro":   c_futuro
        },
        interpretacao=resposta
    )

    # 7. Entrega
    return resposta


if __name__ == "__main__":
    import requests

    print("\n" + "="*50)
    print("   INICIANDO FLUXO - LEITURA 3 CARTAS")
    print("="*50 + "\n")

    # Garante que o usuário de teste existe
    test_uuid = "00000000-0000-0000-0000-000000000001"
    url, headers = db_client.get_supabase_headers()
    requests.post(f"{url}/rest/v1/users", headers=headers, json={"user_id": test_uuid, "nome": "Viajante Teste"})

    pergunta_teste = "Vou conseguir superar as dificuldades e encontrar um novo rumo profissional este ano?"
    resultado = executar_leitura_3_cartas(test_uuid, pergunta_teste)

    print("\n" + "="*50)
    print("   RESPOSTA DA MADAME DO LUAR")
    print("="*50 + "\n")
    print(resultado)
    print("\n" + "="*50 + "\n")
