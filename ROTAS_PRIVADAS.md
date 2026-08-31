# Rotas privadas

Esta versão não mantém nomes públicos semânticos para checkout, webhooks e health. Webhooks e health são derivados de segredo; as rotas do checkout são opacas, porém necessariamente visíveis ao navegador.

1. Configure `PRIVATE_ROUTE_SECRET` no `.env`/Render.
2. Rode:

```powershell
python -m src.private_routes
```

3. Use os caminhos resultantes na configuração dos webhooks e do health check.
4. Compile o checkout normalmente; `PRIVATE_ROUTE_SECRET` não é enviado ao JavaScript.

O `/admin` é a única família de URLs deliberadamente legível e continua protegida por autenticação, CSRF e rate limit.

> Rotas chamadas pelo navegador nunca são realmente secretas para o usuário do navegador; elas aparecem no tráfego de rede. Por isso as rotas de checkout mantêm autenticação e rate limit mesmo usando caminhos derivados.
