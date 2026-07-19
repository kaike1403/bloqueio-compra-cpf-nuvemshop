from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from src.checkout_service import validar_checkout


checkout_bp = Blueprint("checkout", __name__, url_prefix="/api")
limiter = Limiter(key_func=get_remote_address, default_limits=[])


@checkout_bp.route("/validar-checkout", methods=["POST", "OPTIONS"])
@limiter.limit("60 per minute")
def validar_checkout_endpoint():
    """Valida CPF e itens do checkout sem expor dados sensíveis."""
    if request.method == "OPTIONS":
        return ("", 204)

    if request.content_length and request.content_length > 32_768:
        return jsonify({
            "allowed": False,
            "code": "PAYLOAD_TOO_LARGE",
            "message": "A solicitação enviada é muito grande.",
        }), 413

    dados = request.get_json(silent=True)
    resultado = validar_checkout(dados)

    status_http = 400 if resultado.get("code") == "INVALID_PAYLOAD" else 200
    return jsonify(resultado), status_http
