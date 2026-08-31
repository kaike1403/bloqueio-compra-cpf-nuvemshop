# Implantação definitiva

1. Render: use `gunicorn src.app:app` e Health Check `/health`.
2. Para manter SQLite, use Persistent Disk montado em `/var/data` e defina `DATABASE_PATH=/var/data/compras.db`. Como alternativa, migre para PostgreSQL.
3. Configure todas as variáveis de `.env.example` no painel do Render. Nunca envie `.env` ao GitHub.
4. Configure `NUVEMSHOP_APP_SECRET` com o **segredo da aplicação Nuvemshop**. A Nuvemshop envia `X-Linkedstore-Hmac-Sha256`; o backend calcula HMAC-SHA256 sobre o corpo bruto usando `NUVEMSHOP_APP_SECRET`.
5. Configure `CHECKOUT_TOKEN_SECRET` com um segredo longo e diferente de `NUVEMSHOP_APP_SECRET`. Ele assina tokens temporários do endpoint `/api/checkout-token`; nunca é enviado ao JavaScript.
6. Restrinja `CORS_ORIGINS` às origens reais do checkout/loja. A emissão de token também rejeita origens fora dessa lista.
7. Para produção com mais de um worker/instância, use Redis no `RATELIMIT_STORAGE_URI` (por exemplo `redis://...`). `memory://` serve apenas para desenvolvimento ou uma única instância e perde contadores em reinícios.
8. Cloudflare Pages publica a pasta `public`. Gere o frontend dentro de `checkout-validator` com `npm ci && npm run check && npm run build`; o script de build copia automaticamente `dist/main.js` para `public/checkout-validator.js`.
9. Defina `LGPD_RETENCAO_DIAS` conforme a política de retenção aprovada para a operação. A rotina em `banco.py` executa no máximo uma vez a cada 24h: remove registros antigos da tabela operacional `compras` e anonimiza CPF em cancelamentos/logs antigos.
10. Antes de produção, teste: primeira compra, quantidade 2, CPF matematicamente inválido, CPF já pago no dia, pedido pendente, pedido cancelado, token ausente/expirado, rate limit, webhook com HMAC válido/inválido e webhook repetido.
