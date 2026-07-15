# Madame do Luar

Plataforma web de tarot com IA, conta de usuario, creditos, pagamentos, rituais, automacoes, CRM, painel administrativo, LGPD, backup/restore e readiness de producao.

## Estrutura

```text
app/                 Backend FastAPI modular
frontend/            Frontend estatico servido pelo backend
tools/               Scripts operacionais, validadores, workers e backups
architecture/        POPs, contratos, migrations e runbooks tecnicos
docs/checklists/     Checklists de fases e continuidade
docs/reports/        Auditorias e relatorios publicaveis
prompts/             Prompts de IA
tests/               Testes Playwright
imagems/             Assets visuais usados pela experiencia
```

Arquivos locais, caches, backups, `.env`, estados de agentes e historico operacional sensivel ficam fora do Git via `.gitignore`.

## Requisitos

- Python 3.11+
- Node.js 20+
- Conta Supabase
- Chave Gemini
- Credenciais Mercado Pago
- Provedor de email SMTP
- Provedor WhatsApp, quando a promessa comercial estiver ativa

## Setup Local

```powershell
python -m pip install -r requirements.txt
npm install
Copy-Item .env.example .env
```

Preencha o `.env` local com as credenciais reais do ambiente de desenvolvimento. Nunca publique `.env`.

Rodar o sistema:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Acesse:

- App: `http://127.0.0.1:8000`
- Admin: `http://127.0.0.1:8000/admin.html`

## Validacao

```powershell
python -m py_compile app\legacy_api.py tools\validate_public_sale_readiness.py
node --check frontend\app.js
node --check frontend\admin.js
npm.cmd run test:e2e -- --reporter=line
python -B tools\predeploy_check.py --env-file .env.production.example --allow-placeholders
python -B tools\backup_and_restore_check.py
python -B tools\load_smoke_test.py --base-url http://127.0.0.1:8000 --requests 40 --concurrency 8
```

Gate de venda publica:

```powershell
python -B tools\validate_public_sale_readiness.py --live-auth-reading --live-notifications --public-base-url https://madamedoluar.com.br
```

O gate final deve sair sem `FAIL` e sem `BLOCKED` antes de venda publica.

## Producao

O deploy alvo esta modelado em `render.yaml`:

- Web service FastAPI
- Worker de automacoes
- Cron operacional diario
- Cron de backup + restore check
- CORS fechado para `madamedoluar.com.br`
- Segredos com `sync: false`

Antes de publicar:

1. Configure DNS e HTTPS do dominio final.
2. Configure secrets reais no Render.
3. Aplique migrations pendentes no Supabase.
4. Configure o webhook Mercado Pago final.
5. Rode pagamento real controlado.
6. Confirme liberacao automatica de acesso.
7. Rode o gate final completo.

## Status Importante

Este repositório pode ser preparado para GitHub, mas a venda publica depende de provas externas: dominio final, HTTPS, webhook Mercado Pago publico, notificacoes reais e gate final sem bloqueios.

Checklist de continuidade: [docs/checklists/CHECKLIST_MELHORIAS_POR_FASES.md](docs/checklists/CHECKLIST_MELHORIAS_POR_FASES.md)
