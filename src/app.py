import os

from flask import Flask, jsonify
from flask_cors import CORS
from src.lgpd import lgpd_bp
from src.admin import admin_bp
from src.banco import criar_banco
from src.checkout_api import checkout_bp, limiter
from src.config import CORS_ORIGINS
from src.webhook import webhook_bp


def criar_app() -> Flask:
    app = Flask(__name__)
    CORS(
        app,
        resources={
            r"/api/*": {"origins": CORS_ORIGINS},
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

    criar_banco()

    app.register_blueprint(webhook_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(checkout_bp)
    app.register_blueprint(lgpd_bp)

    @app.route("/", methods=["GET"])
    def inicio():
        return jsonify(
            {
                "aplicacao": "Bloqueio de compra por CPF",
                "status": "online",
                "painel": "/admin/",
                "health": "/health",
                "webhook": "/webhooks/pedidos",
            }
        ), 200

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify(
            {
                "status": "ok",
                "versao": "checkout-cpf-053b773",
                "checkout_endpoint": "/api/validar-checkout",
            }
        ), 200

    return app


app = criar_app()


if __name__ == "__main__":
    porta = int(os.getenv("PORT", "5000"))

    app.run(
        host="0.0.0.0",
        port=porta,
        debug=False,
    )