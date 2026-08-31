from __future__ import annotations

import hmac

from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from src.config import RATELIMIT_STORAGE_URI, STORE_ID


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri=RATELIMIT_STORAGE_URI,
    headers_enabled=True,
)


def _bucket_loja(valor_recebido: object) -> str:
    """Impede que um atacante rotacione store_id para criar buckets infinitos."""
    recebido = str(valor_recebido or "").strip()
    esperado = str(STORE_ID or "").strip()

    if esperado and hmac.compare_digest(recebido, esperado):
        return esperado

    return "loja-invalida"


def _store_id_do_json() -> str:
    dados = request.get_json(silent=True)
    if isinstance(dados, dict):
        return _bucket_loja(dados.get("store_id"))
    return "loja-invalida"


def chave_checkout_token() -> str:
    """Rate limit por IP + bucket de loja validado."""
    return f"{get_remote_address()}:{_store_id_do_json()}"


def chave_checkout_validacao() -> str:
    """Rate limit por IP + bucket de loja validado."""
    store_id = request.headers.get("X-Store-ID")
    return f"{get_remote_address()}:{_bucket_loja(store_id)}"
