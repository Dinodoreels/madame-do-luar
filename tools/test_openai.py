import os
from dotenv import load_dotenv

load_dotenv()

# Como o plano menciona OpenAI/Gemini, deixarei a base para ambos.
# Priorizando Gemini devido ao nome do projeto e arquivo (gemini.md).

def test_gemini_connection():
    try:
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            print("❌ GEMINI_API_KEY não encontrada no .env")
            return False
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-pro-latest') # Usando um modelo genérico para testar
        response = model.generate_content("Diga apenas 'Conexão Gemini OK'.")
        
        print(f"✅ Conexão Gemini bem-sucedida! Resposta: {response.text.strip()}")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao conectar com Gemini: {e}")
        return False

if __name__ == "__main__":
    print("Iniciando teste de conexão com IA (Gemini)...")
    test_gemini_connection()
