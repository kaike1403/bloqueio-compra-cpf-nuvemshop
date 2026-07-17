import os

from flask import Flask, jsonify

from src.admin import admin_bp
from src.banco import criar_banco
from src.webhook import webhook_bp

print("=" * 80)
print("APP.PY CARREGADO")
print(__file__)
print("=" * 80)


def criar_app() -> Flask:
    app = Flask(__name__)

    app.secret_key = os.getenv(
        "FLASK_SECRET_KEY",
        "chave-temporaria-desenvolvimento",
    )

    criar_banco()

    app.register_blueprint(webhook_bp)
    app.register_blueprint(admin_bp)

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
            }
        ), 200

    print("ROTAS REGISTRADAS:")
    print(app.url_map)

    return app


app = criar_app()


if __name__ == "__main__":
    porta = int(os.getenv("PORT", "5000"))

    print("=" * 60)
    print("Servidor iniciado")
    print(f"Porta: {porta}")
    print("Painel: /admin/")
    print("Webhook: /webhooks/pedidos")
    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=porta,
        debug=False,
    )