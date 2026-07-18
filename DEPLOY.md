# Implantação definitiva

1. Render: use `gunicorn src.app:app` e Health Check `/health`.
2. Para manter SQLite, use instância paga com Persistent Disk montado em `/var/data` e defina `DATABASE_PATH=/var/data/compras.db`. Como alternativa, migre para Postgres.
3. Configure todas as variáveis de `.env.example` no painel do Render. Nunca envie `.env` ao GitHub.
4. Cadastre/atualize os webhooks `order/created` e `order/updated` com o cabeçalho `X-Webhook-Secret` igual a `WEBHOOK_SECRET`.
5. Cloudflare Pages publica a pasta `public`. A URL do script é `/checkout-validator.js`.
6. Gere o frontend com `npm run check && npm run build` dentro de `checkout-validator`, depois copie `dist/main.js` para `public/checkout-validator.js`.
7. Antes de produção, teste: primeira compra, quantidade 2, CPF já pago no dia, pedido pendente, pedido cancelado e webhook repetido.
