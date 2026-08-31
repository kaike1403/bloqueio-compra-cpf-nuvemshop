# Implantação definitiva

1. No Render, use `gunicorn src.app:app` e configure o health check como `/health`.
2. Para SQLite, use Persistent Disk e defina `DATABASE_PATH=/var/data/compras.db`. Para escala maior, considere PostgreSQL.
3. Copie as variáveis de `.env.example` para o painel do Render. Nunca faça commit do `.env` real.
4. Configure `NUVEMSHOP_APP_SECRET` com o segredo real da aplicação Nuvemshop. Use exclusivamente `NUVEMSHOP_APP_SECRET` para HMAC de webhooks.
5. Gere valores independentes para `FLASK_SECRET_KEY` e `CHECKOUT_TOKEN_SECRET`.
6. Configure `CORS_ORIGINS` somente com as origens reais usadas pela loja/checkout. Se uma origem legítima ficar de fora, a emissão de token receberá 403 e o checkout permanecerá bloqueado por segurança.
7. Em produção com mais de um worker, configure `RATELIMIT_STORAGE_URI` com Redis. `memory://` não compartilha contadores entre processos e perde estado em reinícios.
8. Se desejar reduzir descoberta automatizada do painel, altere `ADMIN_PATH`. Isso é apenas uma camada adicional; mantenha Basic Auth forte e, se possível, Cloudflare Access/VPN/allowlist de IP.
9. Defina `LGPD_RETENCAO_DIAS` de acordo com a política aprovada para a operação.
10. Compile o frontend:

```powershell
cd checkout-validator
npm ci
npm run check
npm run build
```

`npm run build` publica automaticamente o resultado em `public/checkout-validator.js`.

11. Antes do deploy, revise `git status` e `git diff --check` para confirmar que a árvore está limpa e sem problemas de patch/whitespace.

12. Faça testes de produção controlados para: checkout bloqueado desde o primeiro carregamento; CPF válido/inválido; produto não controlado; quantidade acima do limite; compra paga já existente; pedido PIX pendente; token ausente/expirado; rate limit; falha técnica da API com fail-open; HMAC válido/inválido nos quatro webhooks; e tentativa de acesso ao admin com senha incorreta.
