import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_whatsapp_api():
    # Base genérica para a Cloud API oficial do WhatsApp
    token = os.getenv("WHATSAPP_API_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    
    if not token or not phone_id:
        print("❌ WHATSAPP_API_TOKEN ou WHATSAPP_PHONE_NUMBER_ID não encontrados no .env")
        return False
        
    print("✅ Credenciais do WhatsApp encontradas.")
    
    # Endpoint base para verificar conexão (requer configuração completa para não dar erro 400)
    url = f"https://graph.facebook.com/v17.0/{phone_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print("✅ Conexão com WhatsApp API bem-sucedida!")
            return True
        else:
            print(f"⚠️ Atenção ao conectar com WhatsApp: HTTP {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Erro ao testar API do WhatsApp: {e}")
        return False

if __name__ == "__main__":
    print("Iniciando teste de conexão com WhatsApp API...")
    test_whatsapp_api()
