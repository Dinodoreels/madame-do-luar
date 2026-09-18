# Entrega ao programador — 18/09/2026

Repositorio publico: https://github.com/Dinodoreels/madame-do-luar

## Arquitetura encontrada

- Backend Python/FastAPI, entrada `app/main.py`, que importa a aplicacao de `app/legacy_api.py`.
- Modulos de autenticacao, usuarios, leituras, pagamentos, webhooks, rituais, CRM, administracao e analytics em `app/modules/`.
- Frontend HTML/CSS/JavaScript em `frontend/`, servido pelo proprio FastAPI; nao usa React/Next.js.
- Persistencia via Supabase; integracoes de IA, Mercado Pago, email e WhatsApp dependem das variaveis de ambiente.
- Workers e ferramentas operacionais em `tools/`; configuracao de deploy em `render.yaml`; documentacao e migrations em `architecture/`.

## Como executar

```powershell
git clone https://github.com/Dinodoreels/madame-do-luar.git
cd madame-do-luar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm.cmd ci
Copy-Item .env.example .env
```

Copie o exemplo somente em uma instalacao nova, sem sobrescrever um `.env` existente. Configure as credenciais de desenvolvimento e um `JWT_SECRET` aleatorio com pelo menos 32 caracteres. Solicite credenciais por canal privado; elas nao acompanham o GitHub.

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Aplicacao: http://127.0.0.1:8000 — Administracao: http://127.0.0.1:8000/admin.html

## Verificacao desta entrega

- Compilacao dos modulos Python de `app/`: aprovada.
- Sintaxe de `frontend/app.js` e `frontend/admin.js`: aprovada.
- `GET /health`: HTTP 200.
- Playwright existente: 4 testes aprovados, cobrindo desktop e mobile.
- Os testes simulam respostas de cadastro, login, leitura e checkout; nao comprovam pagamentos, IA ou notificacoes reais.
- GitHub confirmado PUBLIC e pagina acessivel por HTTP sem autenticacao.
- Varredura de 250 blobs candidatos a texto no historico: nenhum achado dos padroes de credenciais pesquisados ou dos segredos locais comparados. A checagem nao e uma auditoria completa; binarios e blobs acima de 3 MB nao foram examinados.

## Pontos de atencao

1. O runtime emitiu aviso de fim de suporte de `google.generativeai`; planejar migracao e validar os fluxos de IA.
2. A modularizacao ainda convive com `app/legacy_api.py` e utilitarios em `tools/`; revisar dependencias antes de refatorar.
3. O rate limit usa memoria do processo (`RATE_LIMIT_BUCKETS`); revisar estado compartilhado antes de operar com multiplas instancias.
4. Validar instalacao limpa das dependencias: esta entrega usou o ambiente Python/Node ja instalado na maquina.
5. Antes de venda publica, validar ambiente hospedado, migrations, HTTPS, webhook assinado, pagamento controlado, liberacao de creditos, notificacoes e backup/restore. Nenhuma dessas integracoes externas foi certificada nesta entrega.

Publicar o codigo no GitHub nao publica a aplicacao em um servidor de producao.
