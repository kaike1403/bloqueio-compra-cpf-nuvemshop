from __future__ import annotations

import logging
import os
import re

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import TooManyRequests

from src.admin import admin_bp
from src.banco import criar_banco
from src.checkout_api import checkout_bp
from src.config import (
    CHECKOUT_TOKEN_SECRET,
    CORS_ORIGINS,
    NUVEMSHOP_APP_SECRET,
    PRIVATE_ROUTE_SECRET,
    RATELIMIT_STORAGE_URI,
)
from src.lgpd import lgpd_bp
from src.private_routes import (
    CHECKOUT_TOKEN_PATH,
    CHECKOUT_VALIDATE_PATH,
    HEALTH_PATH,
)
from src.rate_limit import limiter
from src.webhook import webhook_bp


logger = logging.getLogger(__name__)


def _cors_checkout() -> dict[str, object]:
    configuracao = {
        "origins": CORS_ORIGINS,
        "methods": ["POST", "OPTIONS"],
        "allow_headers": [
            "Content-Type",
            "X-Store-ID",
            "X-Checkout-Session",
            "X-Checkout-Token",
        ],
        "supports_credentials": False,
        "max_age": 600,
    }

    # CORS existe somente nas duas rotas usadas pelo NubeSDK.
    return {
        rf"^{re.escape(CHECKOUT_TOKEN_PATH)}$": configuracao,
        rf"^{re.escape(CHECKOUT_VALIDATE_PATH)}$": configuracao,
    }


def criar_app() -> Flask:
    if len(str(PRIVATE_ROUTE_SECRET or "").strip()) < 32:
        raise RuntimeError(
            "PRIVATE_ROUTE_SECRET deve possuir pelo menos 32 caracteres. "
            "Sem ele as rotas privadas não são inicializadas."
        )

    app = Flask(__name__)
    CORS(app, resources=_cors_checkout())

    app.secret_key = os.getenv("FLASK_SECRET_KEY", "").strip()
    if not app.secret_key:
        raise RuntimeError("FLASK_SECRET_KEY não configurada.")

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=32_768,
    )

    limiter.init_app(app)

    if not NUVEMSHOP_APP_SECRET:
        logger.critical(
            "NUVEMSHOP_APP_SECRET ausente: webhooks serão recusados até a configuração ser corrigida."
        )
    if not CHECKOUT_TOKEN_SECRET:
        logger.critical(
            "CHECKOUT_TOKEN_SECRET ausente: autenticação do checkout ficará indisponível."
        )
    if RATELIMIT_STORAGE_URI == "memory://":
        logger.warning(
            "Rate limit usando memory://; em múltiplos workers configure Redis."
        )

    criar_banco()

    app.register_blueprint(webhook_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(checkout_bp)
    app.register_blueprint(lgpd_bp)

    @app.before_request
    def reduzir_superficie_http():
        # O host público não oferece navegação/índice. O admin continua sendo
        # a única família de URLs legíveis por decisão operacional.
        if request.path == "/":
            return "", 404
        return None

    @app.after_request
    def cabecalhos_seguranca(resposta):
        resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        resposta.headers.setdefault("Referrer-Policy", "no-referrer")
        resposta.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        resposta.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
        if request.path != admin_bp.url_prefix:
            resposta.headers.setdefault("Cache-Control", "no-store")
        return resposta

    @app.errorhandler(TooManyRequests)
    def limite_excedido(_erro):
        if request.path in {CHECKOUT_TOKEN_PATH, CHECKOUT_VALIDATE_PATH}:
            return jsonify(
                {
                    "allowed": False,
                    "success": False,
                    "code": "RATE_LIMITED",
                    "message": "Muitas tentativas. Aguarde alguns instantes.",
                }
            ), 429
        return "", 429

    @app.errorhandler(404)
    def nao_encontrado(_erro):
        return "", 404

    @app.errorhandler(405)
    def metodo_nao_permitido(_erro):
        # Não diferencia rota existente de rota inexistente para scanners.
        return "", 404

    @app.route(HEALTH_PATH, methods=["GET"])
    @limiter.limit("30 per minute")
    def health():
        # Caminho derivado de PRIVATE_ROUTE_SECRET; resposta mínima.
        return jsonify({"status": "ok"}), 200

    return app


app = criar_app()


if __name__ == "__main__":
    porta = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=porta, debug=False)
