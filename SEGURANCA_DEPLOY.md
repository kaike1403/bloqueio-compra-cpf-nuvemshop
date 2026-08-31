# Implantação segura

## 1. Segredos

Configure no Render, no mínimo, `FLASK_SECRET_KEY`, `ADMIN_USER`, `ADMIN_PASSWORD`, `CHECKOUT_TOKEN_SECRET`, `NUVEMSHOP_APP_SECRET`, `NUVEMSHOP_STORE_ID`, `NUVEMSHOP_ACCESS_TOKEN` e `NUVEMSHOP_USER_AGENT`.

`NUVEMSHOP_APP_SECRET` é o único segredo usado para validar HMAC-SHA256 dos webhooks. Não mantenha um segundo segredo paralelo para webhooks e nunca coloque `NUVEMSHOP_APP_SECRET`, `CHECKOUT_TOKEN_SECRET`, `ADMIN_PASSWORD` ou `FLASK_SECRET_KEY` no JavaScript público ou no Git.

Gere `FLASK_SECRET_KEY` e `CHECKOUT_TOKEN_SECRET` com valores independentes e longos. Exemplo no PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 2. Webhooks de pedidos e LGPD

Todos os endpoints de webhook validam o corpo bruto com HMAC-SHA256 usando `NUVEMSHOP_APP_SECRET`, conferem `store_id`, limitam o tamanho do payload e rejeitam chamadas sem assinatura válida antes de executar qualquer consulta ou exclusão.

Rotas protegidas:

- `POST /webhooks/pedidos`
- `POST /webhooks/lgpd/store-redact`
- `POST /webhooks/lgpd/customer-redact`
- `POST /webhooks/lgpd/customer-data-request`

As rotas LGPD destrutivas nunca executam exclusões antes de HMAC e loja serem validados. `customer-data-request` responde de forma uniforme e não informa publicamente se um CPF foi localizado.

Se `NUVEMSHOP_APP_SECRET` ou `NUVEMSHOP_STORE_ID` estiverem ausentes, os webhooks retornam 503 em vez de aceitar eventos silenciosamente.

## 3. Checkout e bots

O NubeSDK inicia `cart:validate` em estado `fail` imediatamente. O debounce existe apenas para reduzir chamadas HTTP; ele não cria uma janela em que o checkout fique liberado antes da validação.

Fluxo:

1. checkout inicia bloqueado;
2. `/api/checkout-token` emite token HMAC curto vinculado a `store_id`, `session_id` e `Origin`;
3. `/api/validar-checkout` exige `X-Store-ID`, `X-Checkout-Session` e `X-Checkout-Token`;
4. CPF e regras de produto são validados no backend;
5. somente `allowed: true` libera uma validação normal.

Por decisão operacional deste projeto, indisponibilidade técnica real da infraestrutura é **fail-open**: timeout, falha de rede, rota temporariamente indisponível ou erro 5xx liberam a compra para não interromper vendas. Falhas de segurança/cliente como 400, 401, 403, 413, 422 e 429 permanecem bloqueadas para que um atacante não consiga provocar deliberadamente um erro e ganhar liberação.

Essa proteção reduz bastante automação abusiva, mas um segredo permanente não pode ser mantido secreto em JavaScript. `Origin` também não é uma atestação criptográfica para clientes fora do navegador. Portanto, token curto e rate limit são camadas de redução de abuso, não prova absoluta de origem.

## 4. Rate limit

O projeto usa uma única instância de Flask-Limiter:

- `/api/checkout-token`: 6/min e 30/h por IP + loja;
- `/api/validar-checkout`: 15/min e 120/h por IP + loja;
- `/admin`: tentativas Basic Auth que retornam 401 contam para 5/min e 20/h por IP;
- webhooks possuem limite alto adicional para absorver abuso de rede sem atrapalhar tráfego normal.

Em produção com múltiplos workers/instâncias, configure `RATELIMIT_STORAGE_URI` com Redis. `memory://` deve ser usado apenas em desenvolvimento ou instância única.

## 5. Admin e exposição de rotas

`/` retorna 404 e não publica mapa de endpoints. `/health` retorna apenas `{"status":"ok"}` e não informa versão, painel ou rota de checkout.

O painel continua protegido por Basic Auth, CSRF, cookies `Secure`/`HttpOnly` e rate limit. `ADMIN_PATH` permite trocar `/admin` por um caminho menos óbvio, por exemplo `/gestao-<valor-aleatorio>`. Isso reduz ruído de scanners, mas **não substitui** autenticação. Para proteção mais forte, coloque o painel atrás de Cloudflare Access, VPN ou allowlist de IP.

Webhooks e APIs usadas pelo checkout não podem ser realmente "ocultadas": os chamadores legítimos precisam alcançá-las e o JavaScript público revela as URLs. A proteção correta é autenticação, HMAC, token, CORS, rate limit e respostas mínimas.

## 6. CPF e LGPD

A validação matemática de CPF é centralizada em `src/verificacao.py` e reutilizada em `processador.py`, `checkout_service.py` e na persistência crítica.

Logs técnicos nunca armazenam CPF completo. O formato de máscara é `***.123.456-**`. A migração do banco converte CPFs legados em texto puro na tabela `logs_processamento` para máscara, e mensagens/respostas persistidas passam por sanitização para remover CPFs encontrados em texto.

`LGPD_RETENCAO_DIAS` controla a minimização periódica. No máximo uma vez por 24 horas, `banco.py`:

- remove registros antigos de `compras`;
- anonimiza CPF de `cancelamentos` antigos;
- anonimiza CPF de `logs_processamento` antigos.

Também existe `executar_retencao_lgpd(forcar=True)` para execução administrativa/manutenção. Ajuste o prazo à base legal e às obrigações reais da empresa; 180 dias é apenas o padrão técnico do projeto.

## 7. Build e artefatos

O fonte oficial do checkout é `checkout-validator/src/main.ts`. `npm run build` compila para `checkout-validator/dist/main.js` e publica automaticamente o mesmo conteúdo em `public/checkout-validator.js`.

Não mantenha uma segunda árvore `src/checkout-validator/`. Não envie `.env`, bancos SQLite, `.git`, `node_modules`, `__pycache__` ou artefatos locais contendo dados pessoais.
