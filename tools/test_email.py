import os
import smtplib
from dotenv import load_dotenv

load_dotenv()

def test_email_smtp():
    server = os.getenv("SMTP_SERVER")
    port = os.getenv("SMTP_PORT")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    
    if not all([server, port, user, password]):
        print("❌ Credenciais de SMTP não encontradas no .env")
        return False
        
    try:
        print(f"Tentando conectar ao servidor {server}:{port}...")
        # Assume TLS padrão, ajuste se usar SSL direto
        with smtplib.SMTP(server, int(port)) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            print("✅ Conexão SMTP e Login bem-sucedidos!")
        return True
    except Exception as e:
        print(f"❌ Erro ao testar servidor SMTP: {e}")
        return False

if __name__ == "__main__":
    print("Iniciando teste de conexão de E-mail (SMTP)...")
    test_email_smtp()
