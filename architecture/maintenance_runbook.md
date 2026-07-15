# Manual de Manutencao - Madame do Luar

## Rotina diaria

- Abrir `/admin.html`, aba `Status`.
- Conferir health, alertas, mensagens pendentes e receita.
- Executar `Verificacao diaria` se o cron nao tiver rodado.
- Resolver ou classificar alertas abertos.

## Rotina semanal

- Rodar backup:

```powershell
python tools\backup_database.py
```

- Validar restore do backup mais recente:

```powershell
python tools\restore_database_test.py backups\madame_do_luar_YYYYMMDDTHHMMSSZ.rest.json
```

- Revisar logs de erro em `/admin/status` e `/admin/logs`.
- Conferir Mercado Pago e WhatsApp com testes controlados.

## Rotina mensal

- Revisar `ADMIN_EMAILS`.
- Rodar auditoria de chaves e trocar segredos se necessario.
- Revisar politicas LGPD e textos legais.
- Conferir custos de IA, pagamentos, WhatsApp e hospedagem.

## Modo manutencao

Use o painel admin em `Configuracoes` para bloquear novas leituras e cobrancas PIX durante incidentes ou migracoes.

## Workers

Mantenha apenas um worker por ambiente:

- Local: `scripts/windows/scheduler_automacoes_worker.bat` ou processo manual.
- Producao: Render worker `madame-do-luar-worker`.

Duplicar workers pode enviar mensagens duplicadas.

## Indicadores de alerta

- Muitos `payments.status=pending`.
- `payment_webhook_events.processed=false`.
- `message_events.status=pending` acumulando.
- `notification_logs.status=failed`.
- `readings.status=erro`.
- Health `degraded` ou `down`.
