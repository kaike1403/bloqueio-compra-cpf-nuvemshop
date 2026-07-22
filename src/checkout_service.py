from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.banco import (
    buscar_compra_paga_do_dia,
    normalizar_cpf,
)
from src.produtos_controlados import (
    obter_configuracao_produto,
)


FUSO_HORARIO_LOJA = ZoneInfo("America/Sao_Paulo")


def obter_data_atual_loja() -> str:
    """
    Retorna a data atual da loja no formato YYYY-MM-DD.
    """

    return datetime.now(
        FUSO_HORARIO_LOJA
    ).strftime("%Y-%m-%d")


def normalizar_quantidade(valor: Any) -> int:
    """
    Converte a quantidade recebida para inteiro.
    """

    try:
        quantidade = int(valor)
    except (TypeError, ValueError):
        return 0

    return max(quantidade, 0)


def normalizar_produto_id(valor: Any) -> str:
    """
    Converte o ID do produto para texto.
    """

    if valor is None:
        return ""

    return str(valor).strip()


def cpf_valido(cpf: str) -> bool:
    """Valida tamanho, repetição e dígitos verificadores do CPF."""

    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    for tamanho in (9, 10):
        soma = sum(
            int(cpf[indice]) * (tamanho + 1 - indice)
            for indice in range(tamanho)
        )
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(cpf[tamanho]):
            return False

    return True


def validar_checkout(
    dados: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Aplica as regras de compra antes da criação do pedido.

    Regras atuais:

    1. Se não houver produto controlado, libera.
    2. Se o carrinho possuir mais de uma unidade entre
       produtos controlados, bloqueia.
    3. Se o CPF já possuir compra paga do produto no mesmo
       dia, bloqueia.
    4. Se existir apenas pedido pendente, libera.
    """

    if not isinstance(dados, dict):
        return {
            "allowed": False,
            "code": "INVALID_PAYLOAD",
            "message": "Os dados enviados são inválidos.",
        }

    cpf = normalizar_cpf(dados.get("cpf"))
    itens = dados.get("items")

    if not isinstance(itens, list):
        return {
            "allowed": False,
            "code": "INVALID_PAYLOAD",
            "message": (
                "A lista de produtos do carrinho "
                "não foi enviada corretamente."
            ),
        }

    produtos_controlados: list[dict[str, Any]] = []
    quantidade_total_controlada = 0

    for item in itens:
        if not isinstance(item, dict):
            continue

        produto_id = normalizar_produto_id(
            item.get("product_id")
        )

        if not produto_id:
            continue

        configuracao = obter_configuracao_produto(
            produto_id
        )

        # Produto inexistente ou desativado.
        if not configuracao:
            continue

        if int(configuracao.get("ativo", 0)) != 1:
            continue

        quantidade = normalizar_quantidade(
            item.get("quantity", 1)
        )

        if quantidade <= 0:
            continue

        produto_controlado = {
            "product_id": produto_id,
            "variant_id": item.get("variant_id"),
            "quantity": quantidade,
            "name": (
                item.get("name")
                or configuracao.get("nome_produto")
                or ""
            ),
            "limit": int(
                configuracao.get(
                    "limite_por_cpf",
                    1,
                )
            ),
        }

        produtos_controlados.append(
            produto_controlado
        )

        quantidade_total_controlada += quantidade

    # Nenhum item do carrinho faz parte da regra.
    if not produtos_controlados:
        return {
            "allowed": True,
            "code": "NO_CONTROLLED_PRODUCTS",
            "message": (
                "O carrinho não possui produtos "
                "controlados."
            ),
            "controlled_products": [],
        }

    # Regra geral atual:
    # somente uma unidade entre todos os produtos controlados.
    if quantidade_total_controlada > 1:
        return {
            "allowed": False,
            "code": "QUANTITY_LIMIT",
            "message": (
                "É permitida apenas 1 unidade entre os "
                "produtos deste lançamento."
            ),
        }

    # A quantidade pode ser validada mesmo sem CPF.
    # O próprio checkout da Nuvemshop continuará exigindo
    # o preenchimento do documento.
    if not cpf:
        return {
            "allowed": False,
            "code": "WAITING_FOR_CPF",
            "message": (
                "Aguardando o preenchimento do CPF "
                "para concluir a validação."
            ),
        }

    if not cpf_valido(cpf):
        return {
            "allowed": False,
            "code": "INVALID_CPF",
            "message": (
                "Informe um CPF válido para continuar "
                "a compra."
            ),
        }

    data_atual = obter_data_atual_loja()

    for produto in produtos_controlados:
        compra_paga = buscar_compra_paga_do_dia(
            cpf=cpf,
            produto_id=produto["product_id"],
            data_pedido=data_atual,
        )

        if compra_paga:
            return {
                "allowed": False,
                "code": (
                    "CPF_ALREADY_HAS_PAID_ORDER"
                ),
                "message": (
                    "Este CPF já possui uma compra paga "
                    "deste produto."
                ),
            }

    # Pedidos pendentes não bloqueiam o checkout.
    return {
        "allowed": True,
        "code": "CHECKOUT_ALLOWED",
        "message": "Compra liberada.",
    }