# Relatorio de Auditoria - Estado Atual

Gerado em: `2026-05-18 17:02:21 -0300`
Base local testada: `http://127.0.0.1:8000`

## Resumo

| Status | Total |
|---|---:|
| OK | 16 |
| PARCIAL | 0 |
| BLOQUEADO | 0 |
| FALHA | 1 |

## Evidencias

| Item | Status | Evidencia | Detalhe |
|---|---|---|---|
| Validar login de admin real | OK | Login admin retornou token e role administrativa. |  |
| Validar cadastro novo | OK | Conta nova criada com JWT. |  |
| Validar login de cliente real | OK | Login cliente retornou token e role nao administrativa. |  |
| Validar recuperacao de senha | OK | Forgot, reset e novo login validados. |  |
| Validar carta do dia | OK | Carta retornada: O Mundo. |  |
| Validar painel admin carregando todos os blocos | OK | Dashboard, financeiro, IA, status e alertas responderam 200. |  |
| Validar listagem de usuarios no admin | OK | 10 usuarios retornados. |  |
| Validar alteracao de creditos pelo admin | OK | Credito alterado via endpoint admin. |  |
| Validar logs e auditoria apos acao administrativa | OK | System log e audit log encontrados. |  |
| Validar criacao de tiragem | OK | Reading criada: 7979cab2-7711-40b0-9cc7-3805f012e687. |  |
| Validar consumo de credito por tiragem | OK | Saldo 150 -> 100. |  |
| Validar estorno de credito se a IA falhar | OK | Saldo preservado 200 -> 200; log de falha registrado. |  |
| Validar envio de email | OK | Email enviado via SMTP configurado. |  |
| Validar envio de WhatsApp | FALHA | Uazapi HTTP 503 |  |
| Validar scheduler da carta do dia | OK | Dry-run executado; usuarios=0; agendaveis=0. |  |
| Validar backup | OK | Backup executado; manifesto atualizado. |  |
| Validar restore de teste | OK | Restore de teste validou o arquivo de backup. |  |

## Observacoes

- `OK` significa validado com execucao real ou simulacao explicita permitida pelo ambiente local.
- `PARCIAL` significa que a base tecnica respondeu, mas existe dependencia externa ou validacao complementar.
- `BLOQUEADO` significa dependencia ausente, credencial ausente ou ambiente sem permissao.
- `FALHA` significa erro real observado no fluxo testado.
