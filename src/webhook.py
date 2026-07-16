from typing import Any

from flask import Blueprint, jsonify, request

from src.processador import processar_pedido


webhook_bp = Blueprint(
    "webhook",
    __name__,
)


def extrair_id_do_evento(
    dados: dict[str, Any],
) -> str:
    pedido_id = dados.get("id")

    if pedido_id is None:
        return ""

    return str(pedido_id).strip()


@webhook_bp.route(
    "/webhooks/pedidos",
    methods=["POST"],
)
def receber_webhook_pedido():
    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return jsonify(
            {
                "sucesso": False,
                "erro": "JSON inválido",
            }
        ), 400

    print("\n" + "=" * 70)
    print("WEBHOOK RECEBIDO")
    print("=" * 70)
    print(f"Evento: {dados.get('event')}")
    print(f"Loja: {dados.get('store_id')}")
    print(f"ID recebido: {dados.get('id')}")

    evento = str(
        dados.get("event", "")
    ).strip()

    eventos_permitidos = {
        "order/created",
        "order/updated",
    }

    if evento not in eventos_permitidos:
        print(f"Evento ignorado: {evento}")

        return jsonify(
            {
                "sucesso": True,
                "mensagem": "Evento ignorado",
                "evento": evento,
            }
        ), 200

    pedido_id = extrair_id_do_evento(dados)

    if not pedido_id:
        return jsonify(
            {
                "sucesso": False,
                "erro": "ID do pedido ausente",
            }
        ), 400

    try:
        resultado = processar_pedido(
            pedido_id=pedido_id,
            registrar_no_banco=True,
        )

    except Exception as erro:
        print(f"Erro ao processar webhook: {erro}")

        return jsonify(
            {
                "sucesso": False,
                "erro": "Erro interno no processamento",
            }
        ), 500

    return jsonify(resultado), 200