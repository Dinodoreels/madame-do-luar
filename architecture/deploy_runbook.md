# Runbook de Deploy - Madame do Luar

## Decisao de hospedagem

Provedor definido para primeira producao: Render.

Motivo operacional: o projeto atual e uma API FastAPI que tambem serve frontend estatico. O Render permite modelar, no mesmo `render.yaml`, um web service, um background worker e um cron job. A documentacao oficial do Render tambem informa que custom domains recebem certificados TLS automaticos e redirecionamento HTTP para HTTPS.

Servicos planejados:

- `madame-do-luar-web`: FastAPI + frontend estatico.
- `madame-do-luar-worker`: processamento continuo de automacoes.
- `madame-do-luar-daily-check`: verificacao diaria de operacao.

## Ambientes

Local:

- `APP_ENV=local`
- `APP_BASE_URL=http://localhost:8000`
- CORS com `localhost`, `127.0.0.1` e `null`.
- Usa `.env` local, que nunca deve ser publicado.

Staging:

- `APP_ENV=staging`
- Dominio sugerido: `https://staging.madamedoluar.com.br`
- Supabase separado ou projeto com dados de teste.
- Credenciais sandbox/teste para Mercado Pago, WhatsApp e SMTP.

Producao:

- `APP_ENV=production`
- Dominio alvo: `https://madamedoluar.com.br`
- CORS restrito a `https://madamedoluar.com.br,https://www.madamedoluar.com.br`
- Segredos configurados apenas no Render.

## Secrets

Nao colocar secrets em Git, HTML, JS, CSS ou Markdown publico.

Configurar no Render:

- `ADMIN_EMAILS`
- `JWT_SECRET`
- `GEMINI_API_KEY`
- `OPENAI_API_KEY` se for usado.
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_DB_PASSWORD` se for usar migration/backup Postgres.
- `MERCADO_PAGO_PUBLIC_KEY`
- `MERCADO_PAGO_ACCESS_TOKEN`
- `MERCADO_PAGO_WEBHOOK_SECRET`
- `WHATSAPP_API_URL`
- `WHATSAPP_API_TOKEN`
- `WHATSAPP_TEST_NUMBER`
- `WHATSAPP_DEFAULT_RECIPIENT` se quiser centralizar todas as mensagens WhatsApp do sistema em um numero operacional.
- `SMTP_USER`
- `SMTP_PASS`

Usar `.env.production.example` apenas como checklist.

## Dominio e HTTPS

1. Criar o Blueprint no Render usando `render.yaml`.
2. Conferir o servico `madame-do-luar-web`.
3. Adicionar `madamedoluar.com.br` e `www.madamedoluar.com.br` em Custom Domains.
4. Configurar DNS no provedor do dominio conforme o valor exibido pelo Render.
5. Remover registros `AAAA` conflitantes se existirem.
6. Verificar o dominio no Render.
7. Aguardar emissao de TLS.
8. Testar:

```powershell
python -B tools\deploy_smoke_test.py --base-url https://madamedoluar.com.br
```

## Mercado Pago

Atualizar no painel do Mercado Pago:

- URL de webhook: `https://madamedoluar.com.br/api/webhook/mercado-pago`
- Secret: mesmo valor de `MERCADO_PAGO_WEBHOOK_SECRET`

Depois validar um pagamento sandbox/producao controlado e confirmar:

- `payments.status=approved`
- `credits_released=true`
- evento em `payment_webhook_events`

## Worker e cron

O `render.yaml` cria:

- Worker persistente: `python tools/automation_worker.py`
- Cron diario: `python tools/daily_operation_check.py`

Regra operacional: manter apenas um worker ativo por ambiente para evitar disparos duplicados.

## Deploy

Pre-deploy local:

```powershell
.\scripts\deploy\deploy_render.ps1 -EnvFile .env.production.example -AllowPlaceholders
```

Pre-deploy real antes de publicar:

```powershell
.\scripts\deploy\deploy_render.ps1 -EnvFile .env.production
```

Pos-deploy:

```powershell
python -B tools\deploy_smoke_test.py --base-url https://madamedoluar.com.br
```

## Criterio de pronto

- `/health/detailed` responde `status=ok`.
- `/api/status` responde com integracoes ativas.
- `/admin.html` abre.
- Worker sem erros recorrentes.
- Cron diario executou uma vez.
- Mercado Pago entregou webhook no dominio final.
- `APP_CORS_ORIGINS` nao contem `*`, `null`, `localhost` ou `127.0.0.1`.
