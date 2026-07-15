import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

def test_supabase_connection():
    url: str = os.getenv("SUPABASE_URL")
    key: str = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        print("❌ SUPABASE_URL ou SUPABASE_KEY não encontradas no .env")
        return False
        
    try:
        supabase: Client = create_client(url, key)
        # Tenta buscar uma linha da tabela 'users' apenas para validar a conexão.
        # Se a tabela ainda não existir, retornará um erro que podemos identificar.
        response = supabase.table("users").select("*").limit(1).execute()
        print("✅ Conexão com Supabase bem-sucedida! Status: OK")
        return True
    except Exception as e:
        print(f"⚠️ Atenção ao conectar com Supabase: {e}")
        print("Nota: Se o erro for sobre a tabela não existir, a conexão funcionou, mas a tabela precisa ser criada.")
        return False

if __name__ == "__main__":
    print("Iniciando teste de conexão com Supabase...")
    test_supabase_connection()
