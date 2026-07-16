from flask import Flask, jsonify

from src.admin import admin_bp
from src.banco import criar_banco
from src.webhook import webhook_bp


def criar_app() -> Flask:
    """
    Cria e configura o servidor Flask.
    """

    app = Flask(__name__)

    app.secret_key = "desenvolvimento-local"

    criar_banco()

    app.register_blueprint(webhook_bp)
    app.register_blueprint(admin_bp)

    @app.route("/", methods=["GET"])
    def inicio():
        return jsonify(
            {
                "aplicacao": "Bloqueio de compra por CPF",
                "status": "online",
                "painel": "/admin",
            }
        )

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify(
            {
                "status": "ok",
            }
        )

    return app


app = criar_app()


if __name__ == "__main__":
    print("=" * 60)
    print("Servidor iniciado")
    print("Endereço local: http://127.0.0.1:5000")
    print("Painel: http://127.0.0.1:5000/admin")
    print("Webhook: http://127.0.0.1:5000/webhooks/pedidos")
    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )


import os

if __name__ == "__main__":
    porta = int(os.getenv("PORT", "5000"))

    app.run(
        host="0.0.0.0",
        port=porta,
        debug=False,
    )