from __future__ import annotations

import hashlib
import hmac

from flask import request

from src.config import NUVEMSHOP_APP_SECRET, STORE_ID


ASSINATURA_HEADERS = (
    "X-Linkedstore-Hmac-Sha256",
    "X-Tiendanube-Hmac-Sha256",
    "X-Nuvemshop-Hmac-Sha256",
)


def obter_assinatura_webhook() -> str:
    for nome in ASSINATURA_HEADERS:
        valor = request.headers.get(nome, "").strip()
        if valor:
            return valor
    return ""


def assinatura_valida(
    corpo_bruto: bytes,
    assinatura_recebida: str,
) -> tuple[bool, str]:
    assinatura = str(assinatura_recebida or "").strip().lower()
    segredo = str(NUVEMSHOP_APP_SECRET or "").strip()

    if not assinatura:
        return False, "assinatura_ausente"
    if not segredo:
        return False, "app_secret_ausente"

    assinatura_calculada = hmac.new(
        segredo.encode("utf-8"),
        corpo_bruto,
        hashlib.sha256,
    ).hexdigest()

    if hmac.compare_digest(assinatura, assinatura_calculada):
        return True, "NUVEMSHOP_APP_SECRET_hex"

    return False, "assinatura_invalida"


def loja_webhook_valida(store_id_recebido: object) -> bool:
    store_id_configurado = str(STORE_ID or "").strip()
    if not store_id_configurado:
        return False

    return hmac.compare_digest(
        str(store_id_recebido or "").strip(),
        store_id_configurado,
    )
