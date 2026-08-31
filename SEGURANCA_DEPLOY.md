# Implantação segura

## Segredos

Mantenha exclusivamente no backend: `NUVEMSHOP_APP_SECRET`, `CHECKOUT_TOKEN_SECRET`, `FLASK_SECRET_KEY`, `PRIVATE_ROUTE_SECRET`, credenciais da API e senha do admin. `NUVEMSHOP_APP_SECRET` continua sendo o único segredo usado para validar HMAC-SHA256 da Nuvemshop.

`PRIVATE_ROUTE_SECRET` possui finalidade diferente: derivar URLs não semânticas para reduzir enumeração e scanners genéricos. Não reutilize outro segredo para isso.

## Proteção das rotas

O painel `/admin` permanece legível, mas usa Basic Auth, CSRF, cookies seguros, `Cache-Control: no-store` e rate limit de tentativas inválidas.

As rotas servidor-servidor são derivadas por HMAC-SHA256 de `PRIVATE_ROUTE_SECRET`. As rotas do checkout usam identificadores opacos, sem nomes semânticos; como são consumidas pelo navegador, não são tratadas como segredo. `/` e métodos inválidos retornam 404 vazio.

Webhooks de pedido/LGPD ainda exigem HMAC da Nuvemshop e `store_id`; chamadas com assinatura ou loja inválidas respondem 404 vazio para reduzir enumeração. A obscuridade da URL é apenas uma camada adicional, nunca substitui HMAC.

As duas rotas de checkout continuam protegidas por origem permitida, `store_id`, `session_id`, token HMAC curto e rate limit. Como elas são chamadas por JavaScript no navegador, **não podem ser criptograficamente ocultadas do próprio cliente**: um usuário avançado consegue vê-las na aba Network. O ganho das rotas derivadas é contra descoberta casual/scanners; a segurança real continua sendo token + vínculo de contexto + limites.

O health check usa uma rota derivada e responde apenas `{"status":"ok"}`.

## Bloqueio e interação no checkout

NubeSDK roda em Web Worker e, por desenho, não possui acesso a `document`, `window` ou ao DOM da página. Portanto, o projeto não tenta usar `pointer-events`, listeners DOM ou alterar diretamente o botão da Nuvemshop.

A proteção usa dois mecanismos oficiais:

- `cart:validate = fail` para bloquear o avanço/finalização;
- `modal_content` para abrir um diálogo com backdrop durante a consulta e impedir interações com a página.

O modal é reaplicado se o usuário tentar fechá-lo com Esc/backdrop enquanto a validação ainda estiver pendente. Assim que a validação termina, o slot é limpo. Para não criar deadlock no preenchimento do cadastro, a trava global de interação só é acionada quando já existe CPF com 11 dígitos; antes disso o cliente pode preencher os campos, enquanto o botão de finalizar continua bloqueado.

Uma resposta de regra de negócio negativa desbloqueia a página para correção, mas mantém `cart:validate = fail`. Uma resposta positiva libera tudo. Indisponibilidade técnica segue a decisão operacional fail-open e também libera tudo.

## Fail-open

Fail-open é aplicado apenas a indisponibilidade técnica real: timeout, falha de rede, rota de infraestrutura indisponível ou 5xx. Erros `400`, `401`, `403`, `413`, `422` e `429` permanecem bloqueantes para impedir que um cliente provoque deliberadamente uma falha de segurança e obtenha liberação.

## LGPD e logs

CPF continua validado matematicamente no backend. Logs técnicos devem armazenar somente CPF mascarado (`***.123.456-**`) e a retenção periódica é controlada por `LGPD_RETENCAO_DIAS`.

## Rotação de PRIVATE_ROUTE_SECRET

Rotacionar `PRIVATE_ROUTE_SECRET` altera as URLs servidor-servidor (webhooks e health). Depois da rotação:

1. rode `python -m src.private_routes`;
2. atualize os quatro webhooks na Nuvemshop;
3. atualize o Health Check Path do Render;
4. faça o deploy do backend com o novo segredo.

As URLs do checkout não dependem de `PRIVATE_ROUTE_SECRET`, portanto a rotação não exige republicar o JavaScript do checkout.
