import hmac
import os
import secrets

from flask import Response, abort, request, session


def proteger_admin():
    """Protege o painel /admin com autenticação HTTP Basic."""
    usuario_esperado = os.getenv("ADMIN_USER", "").strip()
    senha_esperada = os.getenv("ADMIN_PASSWORD", "").strip()

    if not usuario_esperado or not senha_esperada:
        return Response("Painel administrativo não configurado.", status=503)

    autenticacao = request.authorization
    usuario_ok = bool(
        autenticacao
        and hmac.compare_digest(autenticacao.username or "", usuario_esperado)
    )
    senha_ok = bool(
        autenticacao
        and hmac.compare_digest(autenticacao.password or "", senha_esperada)
    )

    if usuario_ok and senha_ok:
        return None

    return Response(
        "Autenticação necessária.",
        status=401,
        headers={"WWW-Authenticate": 'Basic realm="Painel Guadalupe"'},
    )


def obter_token_csrf() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validar_csrf_admin() -> None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return

    esperado = session.get("csrf_token", "")
    recebido = request.form.get("csrf_token", "") or request.headers.get(
        "X-CSRF-Token", ""
    )

    if not esperado or not recebido or not hmac.compare_digest(esperado, recebido):
        abort(403, description="Token CSRF inválido.")
