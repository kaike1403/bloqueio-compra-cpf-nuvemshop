# Versão consolidada: rotas privadas + bloqueio de interação

Esta versão preserva as correções anteriores e adiciona endurecimento de rotas e bloqueio visual/interativo durante a validação.

## Incluído

- checkout inicia com `cart:validate = fail`, bloqueando o botão de finalizar antes de qualquer rede/debounce;
- durante uma validação com CPF completo, `modal_content` abre um backdrop e impede interação com a página;
- se o modal for fechado por Esc/backdrop enquanto a validação está pendente, ele é reaplicado;
- ao terminar a validação, a página volta a ser interativa;
- regra de negócio negada mantém o botão bloqueado, mas libera a página para o cliente corrigir CPF/carrinho;
- fail-open somente para indisponibilidade técnica (timeout/rede/404 de infraestrutura/5xx);
- falhas de cliente/segurança 400/401/403/413/422/429 continuam bloqueadas;
- duas rotas do checkout usam identificadores opacos e continuam protegidas por token HMAC curto, loja, sessão, origem e rate limit;
- webhooks de pedidos/LGPD e health usam caminhos derivados de `PRIVATE_ROUTE_SECRET`;
- HMAC + `store_id` permanecem obrigatórios nos quatro webhooks;
- chamadas não autenticadas aos webhooks retornam 404 vazio para reduzir enumeração;
- `/` e métodos inválidos retornam 404 vazio;
- `/admin` permanece a família de URLs legível e segue com Basic Auth + CSRF + rate limit;
- validação matemática de CPF, mascaramento de logs e retenção LGPD permanecem ativos;
- `WEBHOOK_SECRET` não existe; HMAC usa exclusivamente `NUVEMSHOP_APP_SECRET`;
- árvore órfã `src/checkout-validator/`, `script.js` duplicado e `.env.example.txt` foram removidos.

## Limitação técnica importante

NubeSDK executa em Web Worker e não permite acesso a `document`, `window` ou DOM. Portanto não é possível aplicar `pointer-events:none` diretamente à página ou alterar o botão nativo por seletor CSS. O bloqueio de finalização usa `cart:validate`, e a trava de interação usa o slot oficial `modal_content`, que cria um diálogo/backdrop sobre o checkout.

Rotas consumidas pelo JavaScript também não podem ser realmente secretas do próprio navegador; elas podem ser vistas na aba Network. Por isso as rotas do checkout continuam autenticadas mesmo tendo nomes opacos. Webhooks e health, por outro lado, são servidor-servidor e seus caminhos são derivados de segredo.
