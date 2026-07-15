# Runbook de Backup e Restore - Madame do Luar

## Objetivo

Garantir recuperacao do banco antes de operar com usuarios reais, pagamentos, leituras e dados pessoais.

## Backup logico

1. Preferencialmente instalar `pg_dump` e `pg_restore`.
2. Configurar uma conexao de banco no `.env`: `DATABASE_URL`, `SUPABASE_DB_URL`, `POSTGRES_URL` ou `SUPABASE_DB_PASSWORD`.
3. Se a conexao direta/CLI nao estiver disponivel, o script usa fallback por Supabase REST com `SUPABASE_URL` e `SUPABASE_KEY`.
4. Rodar:

```powershell
python tools\backup_database.py
```

O arquivo sera criado em `backups/` por padrao. O manifesto mais recente fica em `backups/latest_backup_manifest.json`.

## Restore testado

1. Para `.dump`, criar um banco isolado, nunca o banco de producao.
2. Configurar `RESTORE_DATABASE_URL` apontando para esse banco.
3. Para `.rest.json`, o script valida o backup e reconstitui os registros em SQLite temporario.
4. Rodar:

```powershell
python tools\restore_database_test.py backups\madame_do_luar_YYYYMMDDTHHMMSSZ.dump
```

ou:

```powershell
python tools\restore_database_test.py backups\madame_do_luar_YYYYMMDDTHHMMSSZ.rest.json
```

O relatorio mais recente fica em `backups/latest_restore_test.json`.

## Evidencia atual

Em 2026-05-17 UTC foi gerado backup operacional por Supabase REST:

- Arquivo: `backups/madame_do_luar_20260517T010855Z.rest.json`
- Manifesto: `backups/latest_backup_manifest.json`
- Tipo: `supabase_rest_json`
- Tamanho: 219579 bytes
- SHA-256: `249b11c9dc7dd985c9f39150b4eb414b0dd486fbcbb3f0946390c5aa0cbd3555`

O teste de restore/integridade foi executado em SQLite temporario:

- Relatorio: `backups/latest_restore_test.json`
- Registros reconstituidos: 126
- Tabelas avaliadas: 32
- Tabelas ignoradas por indisponibilidade/permissao: `admin_customer_notes`, `segment_automation_triggers`

## Supabase Cloud

Segundo a documentacao da Supabase, projetos possuem backups gerenciados e tambem podem gerar backup logico via CLI `supabase db dump`. Restore de PITR/backups depende do plano e do painel/API da Supabase.

## Criterio operacional

- Backup diario configurado ou rotina executavel documentada.
- Restore mensal validado em banco isolado para `.dump` ou validacao local de integridade para `.rest.json`.
- Registro do ultimo backup e restore testado salvo no painel/admin ou em documento operacional.
- Nunca testar restore diretamente no banco de producao.
