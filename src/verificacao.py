import re
from typing import Any


def normalizar_cpf(cpf: str | None) -> str:
    """
    Remove pontos, traços, espaços e qualquer caractere
    que não seja número.
    """

    if not cpf:
        return ""

    return re.sub(r"\D", "", str(cpf))


def cpf_tem_formato_valido(cpf: str | None) -> bool:
    """
    Verifica se o CPF possui exatamente 11 dígitos.

    Esta função valida apenas o formato.
    """

    cpf_limpo = normalizar_cpf(cpf)

    return len(cpf_limpo) == 11


def validar_cpf(cpf: str | None) -> bool:
    """
    Valida matematicamente os dígitos verificadores do CPF.
    """

    cpf_limpo = normalizar_cpf(cpf)

    if len(cpf_limpo) != 11:
        return False

    if cpf_limpo == cpf_limpo[0] * 11:
        return False

    soma_primeiro_digito = sum(
        int(cpf_limpo[indice]) * (10 - indice)
        for indice in range(9)
    )

    resto_primeiro = soma_primeiro_digito % 11

    primeiro_digito = (
        0 if resto_primeiro < 2 else 11 - resto_primeiro
    )

    if primeiro_digito != int(cpf_limpo[9]):
        return False

    soma_segundo_digito = sum(
        int(cpf_limpo[indice]) * (11 - indice)
        for indice in range(10)
    )

    resto_segundo = soma_segundo_digito % 11

    segundo_digito = (
        0 if resto_segundo < 2 else 11 - resto_segundo
    )

    return segundo_digito == int(cpf_limpo[10])


def extrair_cpf_do_pedido(
    pedido: dict[str, Any],
) -> str:
    """
    Procura o CPF nos campos retornados pela Nuvemshop.

    Pela estrutura encontrada na sua loja, os principais campos são:
    - pedido.customer.identification
    - pedido.contact_identification
    """

    customer = pedido.get("customer") or {}

    candidatos = [
        customer.get("identification"),
        pedido.get("contact_identification"),
        customer.get("identification_number"),
        customer.get("document"),
        customer.get("cpf"),
    ]

    for candidato in candidatos:
        cpf = normalizar_cpf(candidato)

        if cpf_tem_formato_valido(cpf):
            return cpf

    return ""


def extrair_produtos_do_pedido(
    pedido: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Retorna uma lista simplificada com os produtos do pedido.
    """

    produtos_encontrados: list[dict[str, Any]] = []

    produtos = pedido.get("products") or []

    if not isinstance(produtos, list):
        return produtos_encontrados

    for item in produtos:
        if not isinstance(item, dict):
            continue

        produto_id = item.get("product_id")
        variante_id = item.get("variant_id")
        sku = item.get("sku") or ""

        nome = (
            item.get("name_without_variants")
            or item.get("name")
            or ""
        )

        quantidade = item.get("quantity", 1)

        try:
            quantidade = int(quantidade)
        except (TypeError, ValueError):
            quantidade = 1

        produtos_encontrados.append(
            {
                "produto_id": produto_id,
                "variante_id": variante_id,
                "sku": sku,
                "nome": nome,
                "quantidade": quantidade,
            }
        )

    return produtos_encontrados


def compra_duplicada(
    cpf_atual: str,
    produto_id: int | str,
    compras_anteriores: list[dict[str, Any]],
) -> bool:
    """
    Verifica se o mesmo CPF já comprou o mesmo product_id.
    """

    cpf_atual_limpo = normalizar_cpf(cpf_atual)
    produto_id_atual = str(produto_id)

    if not cpf_tem_formato_valido(cpf_atual_limpo):
        return False

    for compra in compras_anteriores:
        cpf_anterior = normalizar_cpf(
            compra.get("cpf")
        )

        produto_anterior = str(
            compra.get("produto_id")
        )

        if (
            cpf_anterior == cpf_atual_limpo
            and produto_anterior == produto_id_atual
        ):
            return True

    return False


def mascarar_cpf(cpf: str | None) -> str:
    """
    Retorna o CPF parcialmente oculto para uso em logs.
    """

    cpf_limpo = normalizar_cpf(cpf)

    if len(cpf_limpo) != 11:
        return "***.***.***-**"

    return (
        f"{cpf_limpo[:3]}."
        f"***.***-"
        f"{cpf_limpo[-2:]}"
    )


def teste_verificacao() -> None:
    """
    Teste local das funções principais.
    """

    pedido_teste = {
        "contact_identification": "123.456.789-09",
        "customer": {
            "identification": "123.456.789-09",
        },
        "products": [
            {
                "product_id": 987654,
                "variant_id": 123456,
                "sku": "SKU-TESTE-40",
                "name": "Produto de teste - 40",
                "name_without_variants": "Produto de teste",
                "quantity": 1,
            }
        ],
    }

    cpf = extrair_cpf_do_pedido(pedido_teste)
    produtos = extrair_produtos_do_pedido(
        pedido_teste
    )

    print("CPF localizado:", mascarar_cpf(cpf))
    print("Formato correto:", cpf_tem_formato_valido(cpf))
    print("CPF matematicamente válido:", validar_cpf(cpf))
    print("Produtos encontrados:", len(produtos))

    for produto in produtos:
        print(produto)


if __name__ == "__main__":
    teste_verificacao()