from typing import Any
from datetime import datetime
from zoneinfo import ZoneInfo
from src.banco import (
    atualizar_cancelamentos_do_pedido,
    atualizar_compra_do_pedido,
    atualizar_status_compras_do_pedido,
    buscar_compras_do_dia,
    compra_do_mesmo_pedido_existe,
    criar_banco,
    registrar_cancelamento_pendente,
    registrar_compra,
    registrar_log,
)
from src.cancelamento import (
    cancelar_pedido_nuvemshop,
    resposta_para_texto,
)
from src.config import (
    CANCELAMENTO_REAL_ATIVO,
    MODO_AUTOMATICO,
)
from src.nuvemshop import buscar_pedido
from src.produtos_controlados import produto_esta_controlado
from src.verificacao import (
    extrair_cpf_do_pedido,
    extrair_produtos_do_pedido,
)


MODO_SIMULACAO = True

def pagamento_valido(pedido: dict[str, Any]) -> bool:
    """
    Pedidos pagos e pendentes participam do controle.

    Um pedido pendente já reserva o direito de compra
    daquele CPF durante o dia.
    """

    status_pagamento = str(
        pedido.get("payment_status", "")
    ).lower().strip()

    return status_pagamento in {
        "paid",
        "pending",
    }

def pedido_cancelado(pedido: dict[str, Any]) -> bool:
    """
    Verifica se o pedido já está cancelado.
    """

    status = str(
        pedido.get("status", "")
    ).lower().strip()

    return status == "cancelled"
FUSO_LOJA = ZoneInfo("America/Sao_Paulo")


def obter_data_do_pedido(
    pedido: dict[str, Any],
) -> tuple[str, str]:
    """
    Retorna:
    - data no formato YYYY-MM-DD;
    - data e hora completas normalizadas para São Paulo.
    """

    criado_em = str(
        pedido.get("created_at", "")
    ).strip()

    if not criado_em:
        agora = datetime.now(FUSO_LOJA)

        return (
            agora.strftime("%Y-%m-%d"),
            agora.isoformat(),
        )

    criado_em = criado_em.replace(
        "Z",
        "+00:00",
    )

    try:
        data_hora = datetime.fromisoformat(
            criado_em
        )
    except ValueError:
        agora = datetime.now(FUSO_LOJA)

        return (
            agora.strftime("%Y-%m-%d"),
            agora.isoformat(),
        )

    if data_hora.tzinfo is None:
        data_hora = data_hora.replace(
            tzinfo=FUSO_LOJA
        )
    else:
        data_hora = data_hora.astimezone(
            FUSO_LOJA
        )

    return (
        data_hora.strftime("%Y-%m-%d"),
        data_hora.isoformat(),
    )
def prioridade_pagamento(
    status: str | None,
) -> int:
    status_normalizado = str(
        status or ""
    ).lower().strip()

    prioridades = {
        "paid": 2,
        "pending": 1,
    }

    return prioridades.get(
        status_normalizado,
        0,
    )


def pedido_atual_deve_ser_cancelado(
    pedido_atual: dict[str, Any],
    compra_anterior: dict[str, Any],
) -> bool:
    """
    Pago vence de pendente.

    Se ambos possuem o mesmo status,
    o pedido mais antigo vence.
    """

    status_atual = pedido_atual.get(
        "payment_status"
    )

    status_anterior = compra_anterior.get(
        "status_pagamento"
    )

    prioridade_atual = prioridade_pagamento(
        status_atual
    )

    prioridade_anterior = prioridade_pagamento(
        status_anterior
    )

    if prioridade_atual < prioridade_anterior:
        return True

    if prioridade_atual > prioridade_anterior:
        return False

    atual_criado_em = str(
        pedido_atual.get("created_at", "")
    )

    anterior_criado_em = str(
        compra_anterior.get(
            "pedido_criado_em",
            "",
        )
    )

    return atual_criado_em >= anterior_criado_em



def processar_pedido(
    pedido_id: int | str,
    registrar_no_banco: bool = True,
) -> dict[str, Any]:
    
    """
    Busca e processa um pedido da Nuvemshop.

    Retorna um relatório indicando:
    - se o pedido foi localizado;
    - se o CPF foi localizado;
    - quais produtos são válidos;
    - quais produtos são duplicados;
    - quais produtos foram registrados.

    Em MODO_SIMULACAO, nenhum pedido será cancelado.
    """

    criar_banco()

    resultado: dict[str, Any] = {
        "modo_automatico": MODO_AUTOMATICO,
        "cancelamento_automatico": None,
        "reprocessamento": False,
        "cancelamentos": [],
        "sucesso": False,
        "pedido_id": str(pedido_id),
        "numero_pedido": None,
        "cpf_encontrado": False,
        "pagamento_valido": False,
        "duplicado": False,
        "produtos_duplicados": [],
        "produtos_registrados": [],
        "erros": [],
        "modo_simulacao": MODO_SIMULACAO,
        "cancelamento": None,
    }

    print("\n" + "=" * 70)
    print(f"PROCESSANDO PEDIDO ID {pedido_id}")
    print("=" * 70)

    pedido = buscar_pedido(pedido_id)

    if not pedido:
        mensagem = "Pedido não localizado na API."

        print(mensagem)
        resultado["erros"].append(mensagem)

        return resultado

    numero_pedido = pedido.get("number")
    data_pedido, pedido_criado_em = (
        obter_data_do_pedido(pedido)
    )

    print(f"Data considerada: {data_pedido}")

    resultado["numero_pedido"] = numero_pedido

    print(f"Pedido encontrado: #{numero_pedido}")
    print(f"Status: {pedido.get('status')}")
    print(
        "Status do pagamento: "
        f"{pedido.get('payment_status')}"
    )

    if pedido_cancelado(pedido):
        atualizar_status_compras_do_pedido(
            pedido_id=pedido.get("id"),
            status_pedido=pedido.get("status"),
            status_pagamento=pedido.get("payment_status"),
        )

        mensagem = "Pedido já está cancelado."

        print(mensagem)
        resultado["erros"].append(mensagem)

        return resultado

    if not pagamento_valido(pedido):
        mensagem = (
            "Pedido ainda não está pago. "
            "Nenhum produto será registrado."
        )

        print(mensagem)
        resultado["erros"].append(mensagem)

        return resultado

    resultado["pagamento_valido"] = True

    cpf = extrair_cpf_do_pedido(pedido)

    if not cpf:
        mensagem = "CPF não localizado no pedido."

        print(mensagem)
        resultado["erros"].append(mensagem)

        return resultado

    resultado["cpf_encontrado"] = True

    # Exibe somente parte do CPF no terminal.
    cpf_mascarado = (
        f"{cpf[:3]}.***.***-{cpf[-2:]}"
    )

    print(f"CPF localizado: {cpf_mascarado}")

    produtos = extrair_produtos_do_pedido(pedido)
    produtos_controlados_no_pedido = [
        produto
        for produto in produtos
        if produto_esta_controlado(
            produto.get("produto_id")
        )
    ]

    quantidade_total_controlada = sum(
        int(produto.get("quantidade", 1))
        for produto in produtos_controlados_no_pedido
    )

    if quantidade_total_controlada > 1:
        print(
            "DUPLICADO: o pedido possui mais de uma "
            "unidade entre os produtos controlados."
        )

        resultado["duplicado"] = True

        for produto in produtos_controlados_no_pedido:
            resultado["produtos_duplicados"].append(
                {
                    "produto_id": produto.get(
                        "produto_id"
                    ),
                    "variante_id": produto.get(
                        "variante_id"
                    ),
                    "sku": produto.get("sku"),
                    "nome": produto.get("nome"),
                    "quantidade": produto.get(
                        "quantidade",
                        1,
                    ),
                    "motivo": (
                        "Pedido possui mais de uma unidade "
                        "de produtos controlados"
                    ),
                }
            )


    if not produtos:
        mensagem = "Nenhum produto localizado no pedido."

        print(mensagem)
        resultado["erros"].append(mensagem)

        return resultado

    print(f"Produtos encontrados: {len(produtos)}")
    produtos_vistos_no_pedido: set[str] = set()
    for produto in produtos:
        produto_id = produto.get("produto_id")
        variante_id = produto.get("variante_id")
        sku = produto.get("sku")
        nome = produto.get("nome")
        quantidade = produto.get("quantidade", 1)

        if not produto_esta_controlado(produto_id):
            print(
                "Produto não está na lista de controle. "
                "Nenhuma validação por CPF será aplicada."
            )

            registrar_log(
                resultado="ignorado",
                motivo="Produto não está na lista de controle",
                pedido_id=pedido.get("id"),
                numero_pedido=numero_pedido,
                cpf=cpf,
                produto_id=produto_id,
                variante_id=variante_id,
                sku=sku,
                nome_produto=nome,
            )

            continue

        print("\n" + "-" * 50)
        print(f"Produto: {nome}")
        print(f"Produto ID: {produto_id}")
        print(f"Variante ID: {variante_id}")
        print(f"SKU: {sku}")
        print(f"Quantidade: {quantidade}")

        if not produto_id:
            mensagem = f"Produto sem product_id: {nome}"

            print(mensagem)
            resultado["erros"].append(mensagem)

            continue

        produto_id_texto = str(produto_id)

        if produto_id_texto in produtos_vistos_no_pedido:
            print(
                "DUPLICADO: o mesmo produto aparece mais "
                "de uma vez no próprio pedido."
            )

            resultado["duplicado"] = True

            resultado["produtos_duplicados"].append(
                {
                    "produto_id": produto_id,
                    "variante_id": variante_id,
                    "sku": sku,
                    "nome": nome,
                    "quantidade": quantidade,
                    "motivo": (
                        "Mesmo product_id repetido no pedido"
                    ),
                }
            )
            registrar_log(
                resultado="duplicado",
                motivo="Mesmo product_id repetido no próprio pedido",
                pedido_id=pedido.get("id"),
                numero_pedido=numero_pedido,
                cpf=cpf,
                produto_id=produto_id,
                variante_id=variante_id,
                sku=sku,
                nome_produto=nome,
            )

            continue

        produtos_vistos_no_pedido.add(produto_id_texto)

        # Verifica se uma única linha possui quantidade maior que 1.
        if quantidade > 1:
            print(
                "DUPLICADO: o pedido contém mais de uma "
                "unidade do mesmo produto."
            )

            resultado["duplicado"] = True

            resultado["produtos_duplicados"].append(
                {
                    "produto_id": produto_id,
                    "variante_id": variante_id,
                    "sku": sku,
                    "nome": nome,
                    "quantidade": quantidade,
                    "motivo": (
                        "Quantidade maior que 1 no mesmo pedido"
                    ),
                }
            )
            registrar_log(
                resultado="duplicado",
                motivo="Quantidade maior que 1 no mesmo pedido",
                pedido_id=pedido.get("id"),
                numero_pedido=numero_pedido,
                cpf=cpf,
                produto_id=produto_id,
                variante_id=variante_id,
                sku=sku,
                nome_produto=nome,
            )
            continue
        
        mesmo_pedido_ja_registrado = compra_do_mesmo_pedido_existe(
            pedido_id=pedido.get("id"),
            produto_id=produto_id,
        )

        if mesmo_pedido_ja_registrado:
            atualizar_compra_do_pedido(
                pedido_id=pedido.get("id"),
                produto_id=produto_id,
                status_pedido=pedido.get("status"),
                status_pagamento=pedido.get("payment_status"),
                pedido_criado_em=pedido_criado_em,
                data_pedido=data_pedido,
                quantidade=quantidade,
                variante_id=variante_id,
                sku=sku,
                nome_produto=nome,
            )

            print(
                "REPROCESSAMENTO: este produto já foi registrado "
                "pelo mesmo pedido e teve os status atualizados."
            )

            resultado["reprocessamento"] = True
            registrar_log(
                resultado="reprocessamento",
                motivo="Produto já registrado pelo mesmo pedido",
                pedido_id=pedido.get("id"),
                numero_pedido=numero_pedido,
                cpf=cpf,
                produto_id=produto_id,
                variante_id=variante_id,
                sku=sku,
                nome_produto=nome,
            )
            continue

        compras_anteriores = buscar_compras_do_dia(
            cpf=cpf,
            produto_id=produto_id,
            data_pedido=data_pedido,
            excluir_pedido_id=pedido.get("id"),
        )
        duplicado = bool(compras_anteriores)

        if duplicado:
            print(
                "DUPLICADO: este CPF já possui "
                "esse produto registrado."
            )

            resultado["duplicado"] = True

            resultado["produtos_duplicados"].append(
                {
                    "produto_id": produto_id,
                    "variante_id": variante_id,
                    "sku": sku,
                    "nome": nome,
                    "quantidade": quantidade,
                }
            )
            registrar_log(
                resultado="duplicado",
                motivo="CPF já comprou este produto em outro pedido no mesmo dia",
                pedido_id=pedido.get("id"),
                numero_pedido=numero_pedido,
                cpf=cpf,
                produto_id=produto_id,
                variante_id=variante_id,
                sku=sku,
                nome_produto=nome,
            )
            continue

        print("Produto ainda não comprado por este CPF.")

        if not registrar_no_banco:
            print(
                "Registro ignorado porque "
                "registrar_no_banco=False."
            )
            continue

        registrado = registrar_compra(
            cpf=cpf,
            produto_id=produto_id,
            variante_id=variante_id,
            sku=sku,
            nome_produto=nome,
            quantidade=quantidade,
            pedido_id=pedido.get("id"),
            numero_pedido=numero_pedido,
            status_pedido=pedido.get("status"),
            status_pagamento=pedido.get(
                "payment_status"
            ),
            pedido_criado_em=pedido_criado_em,
            data_pedido=data_pedido,
        )

        if registrado:
            print("Produto registrado no banco.")

            resultado["produtos_registrados"].append(
                {
                    "produto_id": produto_id,
                    "variante_id": variante_id,
                    "sku": sku,
                    "nome": nome,
                    "quantidade": quantidade,
                }
            )
            registrar_log(
                resultado="liberado",
                motivo="Primeira compra válida para este CPF",
                pedido_id=pedido.get("id"),
                numero_pedido=numero_pedido,
                cpf=cpf,
                produto_id=produto_id,
                variante_id=variante_id,
                sku=sku,
                nome_produto=nome,
            )

        else:
            print(
                "Não foi possível registrar. "
                "O produto pode ter sido registrado "
                "por outro processamento."
            )

            resultado["duplicado"] = True

            resultado["produtos_duplicados"].append(
                {
                    "produto_id": produto_id,
                    "variante_id": variante_id,
                    "sku": sku,
                    "nome": nome,
                    "quantidade": quantidade,
                }
            )

    resultado["sucesso"] = True

    print("\n" + "=" * 70)
    print("RESULTADO")
    print("=" * 70)
    print(
        "Produtos registrados: "
        f"{len(resultado['produtos_registrados'])}"
    )
    print(
        "Produtos duplicados: "
        f"{len(resultado['produtos_duplicados'])}"
    )

    if resultado["duplicado"]:
        print(
            "ATENÇÃO: o pedido possui produto duplicado."
        )

        cancelamentos_criados = []

        # Primeiro registra todos os produtos duplicados
        # na fila, mantendo histórico e auditoria.
        for produto_duplicado in resultado[
            "produtos_duplicados"
        ]:
            criado = registrar_cancelamento_pendente(
                pedido_id=pedido.get("id"),
                numero_pedido=numero_pedido,
                cpf=cpf,
                produto_id=produto_duplicado.get(
                    "produto_id"
                ),
                variante_id=produto_duplicado.get(
                    "variante_id"
                ),
                sku=produto_duplicado.get("sku"),
                nome_produto=produto_duplicado.get(
                    "nome"
                ),
                motivo=produto_duplicado.get(
                    "motivo",
                    "CPF já comprou este produto",
                ),
            )

            cancelamentos_criados.append(
                {
                    "produto_id": produto_duplicado.get(
                        "produto_id"
                    ),
                    "criado": criado,
                }
            )

        resultado["cancelamentos"] = cancelamentos_criados

        # O pedido só é cancelado automaticamente quando
        # as duas travas estiverem ativadas.
        if MODO_AUTOMATICO and CANCELAMENTO_REAL_ATIVO:
            print(
                "MODO AUTOMÁTICO ATIVO: "
                "enviando cancelamento à Nuvemshop."
            )

            resultado_cancelamento = (
                cancelar_pedido_nuvemshop(
                    pedido_id=pedido.get("id"),
                    motivo="other",
                )
            )

            resultado["cancelamento_automatico"] = (
                resultado_cancelamento
            )

            resposta_texto = resposta_para_texto(
                resultado_cancelamento
            )

            if resultado_cancelamento.get("cancelado"):
                atualizar_cancelamentos_do_pedido(
                    pedido_id=pedido.get("id"),
                    status="cancelado",
                    resposta_api=resposta_texto,
                )

                registrar_log(
                    resultado="cancelado_automaticamente",
                    motivo=(
                        "Pedido duplicado cancelado "
                        "automaticamente na Nuvemshop"
                    ),
                    pedido_id=pedido.get("id"),
                    numero_pedido=numero_pedido,
                    cpf=cpf,
                )

                print(
                    f"Pedido #{numero_pedido} cancelado "
                    "automaticamente com sucesso."
                )

            else:
                atualizar_cancelamentos_do_pedido(
                    pedido_id=pedido.get("id"),
                    status="erro",
                    resposta_api=resposta_texto,
                )

                registrar_log(
                    resultado="erro_cancelamento",
                    motivo=(
                        "A API não confirmou o cancelamento "
                        "automático do pedido"
                    ),
                    pedido_id=pedido.get("id"),
                    numero_pedido=numero_pedido,
                    cpf=cpf,
                )

                resultado["erros"].append(
                    "A Nuvemshop não confirmou "
                    "o cancelamento automático."
                )

                print(
                    "ERRO: a Nuvemshop não confirmou "
                    "o cancelamento."
                )

        else:
            print(
                "Cancelamento automático desativado. "
                "Pedido mantido na fila de revisão."
            )

    elif resultado["reprocessamento"]:
        print(
            "Webhook repetido: pedido já processado anteriormente."
        )

    else:
        print("Pedido sem duplicidade.")

    print("=" * 70)

    return resultado

def teste_manual() -> None:
    """
    Permite testar com um ID interno de pedido.
    """

    entrada = input(
        "Digite o ID interno do pedido: "
    ).strip()

    if not entrada:
        print("Nenhum ID informado.")
        return

    processar_pedido(
        pedido_id=entrada,
        registrar_no_banco=True,
    )


if __name__ == "__main__":
    teste_manual()