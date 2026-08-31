from __future__ import annotations

import hmac

from flask import Blueprint, jsonify, request

from src.checkout_auth import (
    criar_token_checkout,
    origem_permitida,
    origem_requisicao,
    validar_token_checkout,
)
from src.checkout_service import validar_checkout
from src.config import STORE_ID
from src.rate_limit import (
    chave_checkout_token,
    chave_checkout_validacao,
    limiter,
)


checkout_bp = Blueprint("checkout", __name__, url_prefix="/api")


def _erro(allowed: bool, code: str, message: str, status: int):
    return jsonify(
        {
            "allowed": allowed,
            "success": False,
            "code": code,
            "message": message,
        }
    ), status


@checkout_bp.route("/checkout-token", methods=["POST", "OPTIONS"])
@limiter.limit(
    "6 per minute",
    key_func=chave_checkout_token,
    methods=["POST"],
)
@limiter.limit(
    "30 per hour",
    key_func=chave_checkout_token,
    methods=["POST"],
)
def checkout_token_endpoint():
    """Emite token curto vinculado à loja, sessão e origem do checkout."""
    if request.method == "OPTIONS":
        return ("", 204)

    if request.content_length and request.content_length > 8_192:
        return _erro(False, "PAYLOAD_TOO_LARGE", "Solicitação inválida.", 413)

    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return _erro(False, "INVALID_PAYLOAD", "Solicitação inválida.", 400)

    store_id = str(dados.get("store_id") or "").strip()
    session_id = str(dados.get("session_id") or "").strip()
    store_esperado = str(STORE_ID or "").strip()
    origem = origem_requisicao()

    if not store_id or not session_id:
        return _erro(
            False,
            "INVALID_CHECKOUT_CONTEXT",
            "Contexto do checkout inválido.",
            400,
        )

    if not store_esperado or not hmac.compare_digest(store_id, store_esperado):
        return _erro(False, "INVALID_STORE", "Checkout não autorizado.", 403)

    if not origem_permitida(origem):
        return _erro(False, "INVALID_ORIGIN", "Checkout não autorizado.", 403)

    try:
        token, expira_em = criar_token_checkout(store_id, session_id, origem)
    except RuntimeError:
        # Segredo/configuração ausente é indisponibilidade técnica.
        return _erro(
            False,
            "CHECKOUT_AUTH_UNAVAILABLE",
            "Validação temporariamente indisponível.",
            503,
        )

    return jsonify(
        {
            "success": True,
            "token": token,
            "expires_at": expira_em,
        }
    ), 200


@checkout_bp.route("/validar-checkout", methods=["POST", "OPTIONS"])
@limiter.limit(
    "15 per minute",
    key_func=chave_checkout_validacao,
    methods=["POST"],
)
@limiter.limit(
    "120 per hour",
    key_func=chave_checkout_validacao,
    methods=["POST"],
)
def validar_checkout_endpoint():
    """Valida CPF e itens somente para um checkout autenticado."""
    if request.method == "OPTIONS":
        return ("", 204)

    if request.content_length and request.content_length > 32_768:
        return _erro(
            False,
            "PAYLOAD_TOO_LARGE",
            "A solicitação enviada é muito grande.",
            413,
        )

    store_id = str(request.headers.get("X-Store-ID") or "").strip()
    session_id = str(request.headers.get("X-Checkout-Session") or "").strip()
    token = str(request.headers.get("X-Checkout-Token") or "").strip()
    origem = origem_requisicao()

    token_valido, _motivo = validar_token_checkout(
        token=token,
        store_id=store_id,
        session_id=session_id,
        origem=origem,
    )

    if not token_valido:
        return _erro(
            False,
            "CHECKOUT_UNAUTHORIZED",
            "Checkout não autorizado.",
            401,
        )

    dados = request.get_json(silent=True)
    resultado = validar_checkout(dados)

    status_http = 400 if resultado.get("code") == "INVALID_PAYLOAD" else 200
    return jsonify(resultado), status_http
