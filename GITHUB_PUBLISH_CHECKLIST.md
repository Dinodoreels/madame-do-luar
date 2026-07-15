# GitHub Publish Checklist

Status: preparado localmente, remoto ainda precisa ser criado/conectado.

## Antes do Push

- [x] `.env` ignorado.
- [x] Backups ignorados.
- [x] `node_modules`, `.tmp`, `logs`, `test-results` ignorados.
- [x] Estados locais de agentes ignorados.
- [x] Historico operacional sensivel movido para `docs/internal-local/` e ignorado.
- [x] README publicavel criado.
- [x] Backup e restore testados.
- [x] E2E validado antes da organizacao final.
- [ ] Remote GitHub configurado.
- [ ] Push executado.

## Comandos

```powershell
git status --short
git add .
git commit -m "Prepare Madame do Luar for GitHub publishing"
git remote add origin https://github.com/SEU_USUARIO/madame-do-luar.git
git push -u origin master
```

Se preferir branch `main`:

```powershell
git branch -M main
git push -u origin main
```

## Observacao

Nao publicar o projeto como pronto para venda publica enquanto `tools/validate_public_sale_readiness.py` retornar `FAIL` ou `BLOCKED`.
