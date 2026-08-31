# Versão consolidada de segurança

Esta versão reúne as correções de segurança e a regra operacional de disponibilidade do checkout.

## Incluído

- bloqueio imediato do checkout antes da primeira chamada HTTP;
- fail-open somente para indisponibilidade técnica (timeout/rede/404/5xx/503);
- falhas de cliente/segurança 400/401/403/413/422/429 continuam bloqueadas;
- token HMAC temporário em `/api/checkout-token`, vinculado a loja, sessão e origem;
- autenticação obrigatória em `/api/validar-checkout`;
- rate limit único e centralizado para checkout, admin e webhooks;
- HMAC + `store_id` em webhooks de pedidos e nos três webhooks LGPD;
- validação matemática de CPF centralizada no backend;
- CPF mascarado em logs e sanitização de mensagens/respostas persistidas;
- migração de CPFs legados de logs para máscara;
- retenção/anonimização periódica controlada por `LGPD_RETENCAO_DIAS`;
- `/` sem mapa de rotas e `/health` sem versão/endpoints internos;
- `ADMIN_PATH` configurável, mantendo Basic Auth + CSRF + rate limit;
- fonte TypeScript e `public/checkout-validator.js` sincronizados;
- build publica automaticamente o JS compilado na pasta `public`.

## Observação importante

As URLs consumidas pelo navegador não podem ser mantidas secretas. O caminho do admin pode ser tornado menos óbvio, mas a segurança real permanece em autenticação, HMAC, token, CSRF, rate limit e, idealmente, uma camada externa de acesso administrativo.
