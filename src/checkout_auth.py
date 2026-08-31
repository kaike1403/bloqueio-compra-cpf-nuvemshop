from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import urlparse

from flask import request

from src.config import (
    CHECKOUT_TOKEN_SECRET,
    CHECKOUT_TOKEN_TTL_SECONDS,
    CORS_ORIGINS,
    STORE_ID,
)


TOKEN_VERSION = 1


def _b64url_encode(valor: bytes) -> str:
    return base64.urlsafe_b64encode(valor).decode("ascii").rstrip("=")


def _b64url_decode(valor: str) -> bytes:
    preenchimento = "=" * (-len(valor) % 4)
    return base64.urlsafe_b64decode(valor + preenchimento)


def normalizar_origem(valor: str | None) -> str:
    origem = str(valor or "").strip()
    if not origem:
        return ""

    parsed = urlparse(origem)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""

    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def origem_requisicao() -> str:
    return normalizar_origem(
        request.headers.get("Origin")
        or request.headers.get("Referer")
    )


def origem_permitida(origem: str) -> bool:
    origem_normalizada = normalizar_origem(origem)
    if not origem_normalizada:
        return False

    permitidas = {
        normalizar_origem(item)
        for item in CORS_ORIGINS
        if normalizar_origem(item)
    }
    return origem_normalizada in permitidas


def configuracao_checkout_valida() -> tuple[bool, str]:
    if not str(STORE_ID or "").strip():
        return False, "NUVEMSHOP_STORE_ID não configurado"
    if not str(CHECKOUT_TOKEN_SECRET or "").strip():
        return False, "CHECKOUT_TOKEN_SECRET não configurado"
    return True, ""


def criar_token_checkout(
    store_id: str,
    session_id: str,
    origem: str,
) -> tuple[str, int]:
    configurado, erro = configuracao_checkout_valida()
    if not configurado:
        raise RuntimeError(erro)

    agora = int(time.time())
    expira_em = agora + CHECKOUT_TOKEN_TTL_SECONDS
    payload = {
        "v": TOKEN_VERSION,
        "store_id": str(store_id),
        "session_id": str(session_id or ""),
        "origin": normalizar_origem(origem),
        "iat": agora,
        "exp": expira_em,
    }
    payload_bytes = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    payload_b64 = _b64url_encode(payload_bytes)
    assinatura = hmac.new(
        CHECKOUT_TOKEN_SECRET.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    token = f"{payload_b64}.{_b64url_encode(assinatura)}"
    return token, expira_em


def validar_token_checkout(
    token: str,
    store_id: str,
    session_id: str,
    origem: str,
) -> tuple[bool, str]:
    configurado, erro = configuracao_checkout_valida()
    if not configurado:
        return False, erro

    try:
        payload_b64, assinatura_b64 = str(token or "").split(".", 1)
        assinatura_recebida = _b64url_decode(assinatura_b64)
    except (ValueError, TypeError):
        return False, "token_malformado"

    assinatura_esperada = hmac.new(
        CHECKOUT_TOKEN_SECRET.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(
        assinatura_recebida,
        assinatura_esperada,
    ):
        return False, "assinatura_invalida"

    try:
        payload: dict[str, Any] = json.loads(
            _b64url_decode(payload_b64).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "payload_invalido"

    if payload.get("v") != TOKEN_VERSION:
        return False, "versao_invalida"

    agora = int(time.time())
    try:
        expira_em = int(payload.get("exp", 0))
        emitido_em = int(payload.get("iat", 0))
    except (TypeError, ValueError):
        return False, "tempo_invalido"

    if expira_em <= agora:
        return False, "token_expirado"
    if emitido_em > agora + 30:
        return False, "token_emitido_no_futuro"

    store_esperado = str(STORE_ID or "").strip()
    if not hmac.compare_digest(str(store_id), store_esperado):
        return False, "loja_invalida"
    if not hmac.compare_digest(
        str(payload.get("store_id", "")),
        str(store_id),
    ):
        return False, "loja_token_divergente"

    if not hmac.compare_digest(
        str(payload.get("session_id", "")),
        str(session_id or ""),
    ):
        return False, "sessao_divergente"

    origem_normalizada = normalizar_origem(origem)
    if not origem_permitida(origem_normalizada):
        return False, "origem_nao_permitida"
    if not hmac.compare_digest(
        str(payload.get("origin", "")),
        origem_normalizada,
    ):
        return False, "origem_divergente"

    return True, "ok"
