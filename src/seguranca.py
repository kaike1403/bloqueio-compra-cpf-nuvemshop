import hmac
import os

from flask import Response, request


def proteger_admin():
    """Protege o painel /admin com autenticação HTTP Basic."""

    usuario_esperado = os.getenv("ADMIN_USER", "").strip()
    senha_esperada = os.getenv("ADMIN_PASSWORD", "").strip()

    if not usuario_esperado or not senha_esperada:
        return Response(
            "Painel administrativo não configurado.",
            status=503,
        )

    autenticacao = request.authorization

    usuario_ok = bool(
        autenticacao
        and hmac.compare_digest(
            autenticacao.username or "",
            usuario_esperado,
        )
    )
    senha_ok = bool(
        autenticacao
        and hmac.compare_digest(
            autenticacao.password or "",
            senha_esperada,
        )
    )

    if usuario_ok and senha_ok:
        return None

    return Response(
        "Autenticação necessária.",
        status=401,
        headers={"WWW-Authenticate": 'Basic realm="Painel Guadalupe"'},
    )
