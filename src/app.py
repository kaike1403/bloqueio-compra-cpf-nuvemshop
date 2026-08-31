from __future__ import annotations

import logging
import os

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
    RATELIMIT_STORAGE_URI,
)
from src.lgpd import lgpd_bp
from src.rate_limit import limiter
from src.webhook import webhook_bp


logger = logging.getLogger(__name__)


def criar_app() -> Flask:
    app = Flask(__name__)

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": CORS_ORIGINS,
                "methods": ["POST", "OPTIONS"],
                "allow_headers": [
                    "Content-Type",
                    "X-Store-ID",
                    "X-Checkout-Session",
                    "X-Checkout-Token",
                ],
                "supports_credentials": False,
            },
        },
    )

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
        return resposta

    @app.errorhandler(TooManyRequests)
    def limite_excedido(_erro):
        # Resposta curta e sem informações internas da infraestrutura.
        if request.path.startswith("/api/"):
            return jsonify(
                {
                    "allowed": False,
                    "success": False,
                    "code": "RATE_LIMITED",
                    "message": "Muitas tentativas. Aguarde alguns instantes.",
                }
            ), 429

        return "Muitas tentativas.", 429

    @app.route("/", methods=["GET"])
    def inicio():
        # Não publica mapa de rotas, painel, webhook ou versão da aplicação.
        return "", 404

    @app.route("/health", methods=["GET"])
    def health():
        # Suficiente para o health check sem revelar endpoints internos.
        return jsonify({"status": "ok"}), 200

    return app


app = criar_app()


if __name__ == "__main__":
    porta = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=porta, debug=False)
