# Checklist de Rollback

## Quando acionar

- Health `down` ou `degraded` por mais de 10 minutos.
- Login/cadastro quebrado.
- Pagamentos aprovados sem liberar creditos.
- Webhook Mercado Pago falhando.
- Worker disparando mensagens duplicadas.
- Erro de seguranca ou exposicao de dados.

## Acoes imediatas

- [ ] Ativar modo manutencao no admin se o frontend estiver recebendo usuarios.
- [ ] Pausar worker `madame-do-luar-worker` no Render se houver risco de disparo duplicado.
- [ ] Pausar cron `madame-do-luar-daily-check` se estiver criando alertas em massa.
- [ ] Reverter para o ultimo deploy estavel no Render.
- [ ] Revalidar `/health/detailed`, `/api/status` e `/admin.html`.
- [ ] Conferir pagamentos recentes em `payments` e `payment_webhook_events`.
- [ ] Registrar incidente em `system_logs` pelo painel ou pela rotina operacional.

## Banco de dados

- Nao restaurar backup sobre producao sem validar em banco isolado.
- Se o problema for migration, aplicar SQL corretivo pequeno e documentado.
- Se houver perda/corrupcao, seguir `architecture/backup_restore_runbook.md`.

## Comunicacao

- [ ] Avisar administradores.
- [ ] Se pagamentos foram afetados, listar usuarios e pagamentos impactados.
- [ ] Preparar mensagem curta para clientes se o incidente tiver impacto visivel.
