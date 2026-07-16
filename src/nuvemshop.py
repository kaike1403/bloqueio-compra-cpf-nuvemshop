from typing import Any

import requests

from src.config import obter_headers, obter_url


def fazer_requisicao(
    metodo: str,
    endpoint: str,
    parametros: dict | None = None,
    dados: dict | None = None,
) -> Any:
    url = obter_url(endpoint)

    try:
        resposta = requests.request(
            method=metodo,
            url=url,
            headers=obter_headers(),
            params=parametros,
            json=dados,
            timeout=30,
        )

        resposta.raise_for_status()

        if not resposta.content:
            return {}

        return resposta.json()

    except requests.exceptions.HTTPError as erro:
        print(
            f"Erro HTTP {erro.response.status_code} "
            f"em {endpoint}"
        )
        print(f"Resposta da API: {erro.response.text}")

    except requests.exceptions.RequestException as erro:
        print(f"Erro na requisição: {erro}")

    return None

def buscar_pedido(
    pedido_id: int | str,
) -> dict:
    """
    Busca um pedido pelo ID interno.
    """

    resultado = fazer_requisicao(
        metodo="GET",
        endpoint=f"/orders/{pedido_id}",
    )

    if isinstance(resultado, dict):
        return resultado

    return {}


def listar_pedidos(
    pagina: int = 1,
    por_pagina: int = 30,
) -> list[dict]:
    """
    Lista pedidos da loja.
    """

    parametros = {
        "page": pagina,
        "per_page": por_pagina,
    }

    resultado = fazer_requisicao(
        metodo="GET",
        endpoint="/orders",
        parametros=parametros,
    )

    if isinstance(resultado, list):
        return resultado

    return []


def buscar_pedido_por_numero(
    numero_pedido: int,
    limite_paginas: int = 20,
) -> dict:
    """
    Localiza um pedido pelo número exibido no painel.
    Exemplo: pedido #614.
    """

    for pagina in range(1, limite_paginas + 1):
        pedidos = listar_pedidos(
            pagina=pagina,
            por_pagina=30,
        )

        if not pedidos:
            break

        for pedido in pedidos:
            try:
                numero = int(pedido.get("number"))
            except (TypeError, ValueError):
                continue

            if numero == numero_pedido:
                return pedido

        if len(pedidos) < 30:
            break

    return {}


def cancelar_pedido(
    pedido_id: int | str,
    motivo: str = "Compra duplicada para o mesmo CPF",
) -> bool:
    """
    Tenta cancelar um pedido.

    Atenção:
    o endpoint exato de cancelamento pode variar conforme
    as permissões e recursos disponíveis na API.
    """

    dados = {
        "cancel_reason": motivo,
    }

    resultado = fazer_requisicao(
        metodo="POST",
        endpoint=f"/orders/{pedido_id}/cancel",
        dados=dados,
    )

    return resultado is not None


def resumo_pedido(
    pedido: dict,
) -> dict:
    """
    Retorna apenas os campos relevantes do pedido.
    """

    customer = pedido.get("customer") or {}

    return {
        "pedido_id": pedido.get("id"),
        "numero_pedido": pedido.get("number"),
        "cpf": (
            customer.get("identification")
            or pedido.get("contact_identification")
            or ""
        ),
        "status": pedido.get("status"),
        "payment_status": pedido.get("payment_status"),
        "produtos": pedido.get("products") or [],
    }


def teste_busca() -> None:
    """
    Teste manual com um ID interno.
    """

    entrada = input(
        "Digite o ID interno do pedido: "
    ).strip()

    if not entrada:
        print("Nenhum ID informado.")
        return

    pedido = buscar_pedido(entrada)

    if not pedido:
        print("Pedido não encontrado.")
        return

    resumo = resumo_pedido(pedido)

    print("\nPedido localizado:")
    print(f"ID: {resumo['pedido_id']}")
    print(f"Número: #{resumo['numero_pedido']}")
    print(f"CPF localizado: {bool(resumo['cpf'])}")
    print(f"Status: {resumo['status']}")
    print(f"Pagamento: {resumo['payment_status']}")
    print(f"Produtos: {len(resumo['produtos'])}")


if __name__ == "__main__":
    teste_busca()