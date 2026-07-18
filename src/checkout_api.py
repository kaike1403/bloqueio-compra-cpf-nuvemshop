from __future__ import annotations

from flask import Blueprint, jsonify, request

from src.checkout_service import validar_checkout


checkout_bp = Blueprint(
    "checkout",
    __name__,
    url_prefix="/api",
)


@checkout_bp.route(
    "/validar-checkout",
    methods=["POST", "OPTIONS"],
)
def validar_checkout_endpoint():
    """
    Recebe os dados do checkout e verifica se a compra
    pode continuar.

    Endpoint:
        POST /api/validar-checkout
    """

    # Resposta para a verificação prévia de CORS.
    if request.method == "OPTIONS":
        resposta = jsonify({"ok": True})
        resposta.status_code = 204
        return resposta

    dados = request.get_json(silent=True)

    resultado = validar_checkout(dados)

    status_http = 200

    if resultado.get("code") == "INVALID_PAYLOAD":
        status_http = 400

    resposta = jsonify(resultado)
    resposta.status_code = status_http

    return adicionar_cabecalhos_cors(resposta)


def adicionar_cabecalhos_cors(resposta):
    """
    Libera temporariamente chamadas externas durante os testes.

    Posteriormente restringiremos para os domínios oficiais
    da Guadalupe e da Nuvemshop.
    """

    resposta.headers["Access-Control-Allow-Origin"] = "*"
    resposta.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization"
    )
    resposta.headers["Access-Control-Allow-Methods"] = (
        "POST, OPTIONS"
    )

    return resposta