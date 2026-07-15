import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def chamar_madame_do_luar(prompt_base_path, **kwargs):
    """
    Wrapper para invocar a IA (Gemini) usando a persona e um prompt base.
    Substitui as variáveis em **kwargs no texto do prompt.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY não encontrada no .env. Preencha o arquivo para testar a IA.")
        
    genai.configure(api_key=api_key)
    
    # Utilizando o modelo padrão de texto atualizado
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Carrega a Constituição da Persona
    project_root = os.path.dirname(os.path.dirname(__file__))
    persona_path = os.path.join(project_root, "docs", "product", "persona.md")
    
    try:
        with open(persona_path, "r", encoding="utf-8") as f:
            persona = f.read()
    except FileNotFoundError:
        persona = "Você é Madame do Luar, uma taróloga mística."

    # Carrega o Prompt Base (da pasta prompts/)
    prompt_path = os.path.join(project_root, prompt_base_path)
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
        
    # Inject variables
    prompt_final = prompt_template
    for key, value in kwargs.items():
        prompt_final = prompt_final.replace(f"{{{key}}}", str(value))
        
    # Monta a requisição final
    conteudo_requisicao = f"PERSONA E REGRAS:\n{persona}\n\n---\n\nINSTRUÇÕES PARA ESTA TAREFA:\n{prompt_final}"
    
    # Faz a chamada real à API
    response = model.generate_content(conteudo_requisicao)
    return response.text
