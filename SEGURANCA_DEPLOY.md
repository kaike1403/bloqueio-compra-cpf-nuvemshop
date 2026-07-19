# Implantação segura

1. No Render, configure `FLASK_SECRET_KEY`, `ADMIN_USER`, `ADMIN_PASSWORD` e `WEBHOOK_SECRET` com valores longos e únicos.
2. Cadastre ou atualize os webhooks `order/created` e `order/updated` incluindo o cabeçalho customizado `X-Webhook-Secret` com o mesmo valor de `WEBHOOK_SECRET`.
3. Configure `CORS_ORIGINS` somente com as origens reais observadas no checkout. Não use `*`.
4. Use Persistent Disk e `DATABASE_PATH=/var/data/compras.db`, ou migre para PostgreSQL.
5. Faça deploy e teste `/health`, o checkout e o webhook autorizado/não autorizado.
6. O checkout está em modo fail-open: queda do backend não bloqueia vendas, mas o webhook deve revalidar pedidos controlados.

## Gerar segredos no PowerShell

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Execute duas vezes: uma para `FLASK_SECRET_KEY` e outra para `WEBHOOK_SECRET`.
