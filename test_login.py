import requests
try:
    resp = requests.post("http://localhost:8000/auth/login", json={"email": "slumacademyoficial@gmail.com", "senha": "test"})
    print("STATUS", resp.status_code)
    print("TEXT", resp.text)
except Exception as e:
    print("ERR", e)
