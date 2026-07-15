# Checklist Final de Go-Live - Madame do Luar

Data de preparacao: 2026-05-17

Este checklist separa prontidao tecnica interna de publicacao externa. O sistema
so deve receber trafego publico depois que os itens de conta, dominio, DNS,
webhook e secrets reais forem confirmados fora do repositorio.

## 0. Regra de venda publica

O Madame do Luar so pode ser considerado pronto para venda publica quando o gate
executavel abaixo retornar sem `FAIL` e sem `BLOCKED`:

```bash
python -B tools/validate_public_sale_readiness.py --env-file .env.production --live-auth-reading --live-notifications --public-base-url https://madamedoluar.com.br
```

Para diagnostico local, rode:

```bash
python -B tools/validate_public_sale_readiness.py
```

Status real em 2026-05-17: ainda nao pronto para venda publica. O gate ao vivo
com rede liberada passou em cadastro, login, perfil, carta do dia autenticada,
leitura de 3 cartas com IA real, email SMTP, WhatsApp real, admin, logs,
documentos legais e qualidade textual do frontend. Continuam bloqueados:
pagamento real no ambiente final, webhook automatico liberando acesso sem
intervencao manual e deploy HTTPS no dominio final, porque `APP_BASE_URL` e
`MERCADO_PAGO_NOTIFICATION_URL` ainda apontam para a URL temporaria
`https://<tunnel-temporario>`.

## 1. LGPD e documentos legais

- [x] `/privacidade.html` publicado no frontend.
- [x] `/termos.html` publicado no frontend.
- [x] `/ia.html` publicado no frontend.
- [x] Cadastro exige aceite de termos, privacidade e aviso de IA.
- [x] API possui exportacao LGPD em `GET /api/lgpd/export`.
- [x] API possui exclusao/anonimizacao em `DELETE /api/lgpd/account`.
- [ ] Revisao juridica profissional concluida antes de campanhas em escala.

## 2. Monitoramento e operacao

- [x] Health detalhado em `/health/detailed`.
- [x] Painel interno de status em `/admin/status`.
- [x] Metricas de conversao, retencao e receita no admin.
- [x] Rotina diaria executavel em `tools/daily_operation_check.py`.
- [x] Cron de producao modelado em `render.yaml`.
- [ ] Alertas revisados diariamente por responsavel operacional.

## 3. Backup e restore

- [x] Backup REST/Supabase executavel por `tools/backup_database.py`.
- [x] Restore/integridade validavel por `tools/restore_database_test.py`.
- [x] Runbook em `architecture/backup_restore_runbook.md`.
- [ ] Backup Postgres `.dump` habilitado quando `SUPABASE_DB_PASSWORD` ou `DATABASE_URL` estiver disponivel.
- [ ] Restore Postgres real testado em banco isolado antes de migracoes destrutivas.

## 4. Deploy publico

- [x] Provedor recomendado definido: Render.
- [x] Blueprint `render.yaml` com web, worker e cron.
- [x] Secrets fora do codigo via `sync: false` e `generateValue`.
- [x] CORS de producao limitado a dominios HTTPS.
- [x] Script de pre-deploy em `deploy_render.ps1`.
- [x] Smoke test pos-deploy em `tools/deploy_smoke_test.py`.
- [ ] Blueprint sincronizado na conta Render.
- [ ] Dominios `madamedoluar.com.br` e `www.madamedoluar.com.br` apontados no DNS.
- [ ] HTTPS emitido e ativo no provedor.
- [ ] Webhook Mercado Pago final configurado para `https://madamedoluar.com.br/api/webhook/mercado-pago`.
- [ ] Smoke test publico executado contra `https://madamedoluar.com.br`.

## 5. Gates finais antes de trafego pago

- [ ] `python -B tools/validate_public_sale_readiness.py --env-file .env.production --live-auth-reading --live-notifications --public-base-url https://madamedoluar.com.br` aprovado sem `FAIL`/`BLOCKED`.
- [ ] `python -B tools/predeploy_check.py --env-file .env.production` sem placeholders.
- [ ] `python tools/verify_schema_phase3.py` aprovado contra Supabase de producao.
- [ ] `python tools/validate_mercado_pago_checkout.py` aprovado no ambiente final.
- [ ] `python tools/validate_mercado_pago_webhook_e2e.py` aprovado no webhook final.
- [ ] `python tools/validate_relationship_sprint.py` aprovado com numero de teste real.
- [ ] `python tools/validate_production_sprint.py` aprovado no ambiente final.
- [ ] Responsavel de rollback definido e com acesso ao Render, Supabase e Mercado Pago.
