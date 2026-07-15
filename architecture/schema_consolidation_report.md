# Relatorio de Consolidacao do Schema

Data: 2026-05-17

## Fonte canonica

O arquivo canonico de banco da plataforma e `architecture/schema.sql`.

Ele consolida:

- base inicial de usuarios, leituras, cartas, pagamentos e mensagens;
- autenticacao propria com hash de senha e JWT;
- operacao admin, planos, pacotes, cupons, prompts, alertas e fila de reprocessamento;
- automacoes, notificacoes, LGPD, CRM, monetizacao e metricas operacionais.

As migrations em `architecture/migration_*.sql` ficam como historico incremental e apoio para aplicacao parcial. Para um ambiente novo, o caminho recomendado e aplicar `architecture/schema.sql` inteiro.

## Contrato operacional

- O backend deve considerar `architecture/schema.sql` como contrato de estrutura.
- Novas tabelas, colunas, indices, RPCs e triggers devem entrar primeiro no schema consolidado.
- Migrations incrementais continuam permitidas, mas nao podem divergir do consolidado.
- A verificacao real deve ser feita com `python tools\verify_schema_phase3.py` contra o Supabase alvo.

## Status

O schema foi revisado como parte da Sprint 1 para remover a ambiguidade entre migrations antigas e a base atual. O plano de implantacao passa a tratar o schema consolidado como fonte de verdade; notas antigas sobre tabelas ausentes ficam substituidas por validacoes reais mais recentes.
