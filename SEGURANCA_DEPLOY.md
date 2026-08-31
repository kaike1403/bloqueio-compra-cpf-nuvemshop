# Implantação segura

## Segredos e webhooks

Configure no Render `FLASK_SECRET_KEY`, `ADMIN_USER`, `ADMIN_PASSWORD`, `CHECKOUT_TOKEN_SECRET` e `NUVEMSHOP_APP_SECRET` com valores fortes. `NUVEMSHOP_APP_SECRET` deve ser exatamente o segredo da aplicação cadastrado na Nuvemshop e é a única variável usada para validar HMAC dos webhooks. Não mantenha um segundo segredo paralelo para webhooks.

Os webhooks de pedidos e LGPD exigem `X-Linkedstore-Hmac-Sha256` (com aliases compatíveis aceitos pelo código) calculado sobre o corpo bruto com HMAC-SHA256. Se `NUVEMSHOP_APP_SECRET` não estiver configurado, esses endpoints registram erro e retornam HTTP 503; não aceitam o evento silenciosamente.

## Checkout público

`/api/validar-checkout` não aceita mais chamadas anônimas. O NubeSDK envia `store.id` e `session.id` para `/api/checkout-token`; o backend só emite um token HMAC temporário quando o `store_id` corresponde a `NUVEMSHOP_STORE_ID` e a origem pertence a `CORS_ORIGINS`. A validação exige `X-Store-ID`, `X-Checkout-Session` e `X-Checkout-Token`.

`CHECKOUT_TOKEN_SECRET` permanece somente no backend. O token emitido é de curta duração (padrão: 300 segundos), vinculado à loja, origem e sessão. Essa camada reduz fortemente o uso casual do endpoint como oráculo, mas **não é atestação criptográfica da origem do navegador**: um atacante fora do browser pode falsificar `Origin`. Por isso, o rate limit e a rotação de segredo continuam obrigatórios.

Para exigência de atestação criptográfica de origem, use um mecanismo assinado pela própria plataforma. A Nuvemshop documenta App Proxies com `X-Linkedstore-HMAC-Sha256`, assinado com o segredo da aplicação, mas esse recurso é descrito para storefront e depende de configuração pela Nuvemshop. Antes de trocar o fluxo do checkout para App Proxy, confirme com o suporte/parcerias da Nuvemshop que o proxy está disponível e suportado no contexto do checkout da sua aplicação. Não coloque `NUVEMSHOP_APP_SECRET` nem outro segredo permanente no JavaScript público.

Limites atuais: emissão de token `6/min` e `30/h` por IP+loja; validação de checkout `15/min` e `120/h` por IP+loja; autenticação Basic do `/admin` `5/min` e `20/h` por IP, contabilizando respostas 401. Em produção distribuída, configure `RATELIMIT_STORAGE_URI` com Redis para compartilhar os contadores entre workers.

## CPF e LGPD

O backend valida matematicamente o CPF antes de consultar/registrar compras. Logs técnicos recebem apenas CPF mascarado no padrão `***.123.456-**`; registros legados de `logs_processamento` são mascarados na migração. Respostas de erro da API também passam por sanitização antes de serem impressas ou persistidas como texto de auditoria.

`LGPD_RETENCAO_DIAS` define a janela de retenção do índice operacional. `banco.py` executa uma rotina de minimização no máximo uma vez a cada 24 horas: registros antigos de `compras` são removidos, e CPFs antigos de `cancelamentos` e `logs_processamento` são anonimizados. Ajuste o prazo à base legal e às obrigações de retenção da empresa; o valor padrão do projeto é 180 dias.

## Geração de segredos

No PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Gere valores independentes para `FLASK_SECRET_KEY` e `CHECKOUT_TOKEN_SECRET`. `NUVEMSHOP_APP_SECRET` não deve ser inventado: use o segredo fornecido no cadastro da aplicação Nuvemshop.
