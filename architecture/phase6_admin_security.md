# Fase 6 - Painel Administrativo Profissional

## Objetivo

Transformar o admin em uma superficie operacional segura, auditavel e com permissoes granulares.

## RBAC

Perfis suportados:

- `super_admin`: acesso total.
- `admin`: operacao geral, sem aprovacao financeira sensivel.
- `financeiro`: pagamentos, planos, pacotes, cupons e aprovacao manual.
- `suporte`: usuarios, CRM e logs.
- `marketing`: CRM, campanhas, conteudo e exportacoes.
- `operacoes`: jobs, alertas, status e auditoria operacional.

Implementacao:

- `app/modules/admin/security.py`
- `ROLE_PERMISSIONS`
- `require_permission(permission)`

## Acoes Sensiveis

Aprovacao manual de pagamento exige:

- permissao `admin.billing.approve`;
- reautenticacao por `X-Admin-Confirm-Password`; ou
- codigo por `X-Admin-2FA-Code` quando `ADMIN_2FA_CODE` ou `ADMIN_REAUTH_CODE` estiver configurado.

Toda reautenticacao sensivel registra auditoria `ADMIN_SENSITIVE_REAUTH`.

## Dados Sensiveis

Email e WhatsApp sao mascarados por padrao em:

- `GET /api/admin/users`
- `GET /api/admin/users/{user_id}`
- `GET /api/admin/crm`
- `GET /api/admin/crm/users/{user_id}`

Para revelar, usar `reveal=true`. Esse uso gera auditoria.

## Exportacao

`GET /api/admin/crm/export.csv` exige `admin.export` e registra `ADMIN_CRM_EXPORT_CREATED`.

## Novos Painéis

- `GET /api/admin/dashboard/financial`
- `GET /api/admin/errors/summary`

## Migration

`architecture/migration_phase6_admin_security.sql` prepara:

- novos roles em `users.role`;
- campos de 2FA;
- indices;
- colunas auxiliares de auditoria.
