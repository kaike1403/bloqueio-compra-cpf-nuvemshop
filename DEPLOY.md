# Implantação definitiva

## 1. Variáveis obrigatórias

No Render configure todas as variáveis de `.env.example`. Além dos segredos anteriores, esta versão exige `PRIVATE_ROUTE_SECRET` com pelo menos 32 caracteres. Use um valor independente de `NUVEMSHOP_APP_SECRET`, `CHECKOUT_TOKEN_SECRET` e `FLASK_SECRET_KEY`.

Exemplo para gerar cada segredo no PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Nunca faça commit do `.env` real.

## 2. Banco e rate limit

Para SQLite no Render, use Persistent Disk e defina `DATABASE_PATH=/var/data/compras.db`. Em múltiplos workers/instâncias, use Redis em `RATELIMIT_STORAGE_URI`; `memory://` não compartilha contadores entre processos.

## 3. Rotas privadas

As rotas servidor-servidor (webhooks e health) são derivadas por HMAC-SHA256 a partir de `PRIVATE_ROUTE_SECRET` e não ficam gravadas em texto claro no fonte Python. As duas rotas do checkout usam nomes opacos fixos, porque precisam existir no JavaScript público e seriam descobertas de qualquer forma pela aba Network. O painel continua em `ADMIN_PATH`, normalmente `/admin`.

Depois de configurar o `.env`, descubra os caminhos derivados:

```powershell
python -m src.private_routes
```

A saída mostrará os caminhos de:

- webhook de pedidos;
- três webhooks LGPD;
- health check;
- token do checkout;
- validação do checkout.

Configure na Nuvemshop os quatro caminhos de webhook retornados pelo comando. No Render, configure o Health Check Path com o valor de `HEALTH_PATH`. As duas rotas de checkout aparecem apenas para conferência; elas são opacas, mas não secretas.

**Atenção:** não altere `PRIVATE_ROUTE_SECRET` sem também atualizar os webhooks na Nuvemshop e o Health Check Path. A rotação muda as rotas servidor-servidor.

## 4. Build do checkout

Compile o frontend normalmente; as duas URLs do checkout já são opacas e coincidem entre backend e JavaScript:

```powershell
cd checkout-validator
npm ci
npm run check
npm run build
```

O resultado final é publicado em `public/checkout-validator.js`. `PRIVATE_ROUTE_SECRET` continua obrigatório no backend para webhooks/health, mas não é colocado no JavaScript público.

## 5. Regra do checkout

O fluxo final é:

1. `cart:validate` nasce em `fail`, portanto o botão de finalizar já inicia bloqueado;
2. quando existe CPF completo e uma validação está pendente, o app abre `modal_content`, cujo backdrop impede interação com a página;
3. a API valida token, loja, sessão, CPF e regras de compra;
4. resposta normal `allowed: true` libera botão e página;
5. resposta normal `allowed: false` mantém somente o checkout bloqueado e devolve a interação para que o cliente possa corrigir CPF/carrinho;
6. falha técnica real (timeout, rede, 404 de infraestrutura ou 5xx) aplica **fail-open**: libera botão e página;
7. falhas de segurança/cliente (`400`, `401`, `403`, `413`, `422`, `429`) não aplicam fail-open.

## 6. Testes antes do deploy

Valide pelo menos: CPF válido/inválido, produto não controlado, quantidade acima do limite, compra paga existente, PIX pendente, token ausente/expirado, rate limit, indisponibilidade da API com fail-open, HMAC válido/inválido em todos os webhooks, Basic Auth/CSRF do admin e fechamento manual do modal durante uma validação.
