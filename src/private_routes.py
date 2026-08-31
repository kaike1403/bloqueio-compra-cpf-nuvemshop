from __future__ import annotations

import hashlib
import hmac

from src.config import PRIVATE_ROUTE_SECRET


_PREFIXO = "/_nsv"

# As rotas do checkout precisam existir no JavaScript público e, portanto,
# não podem ser tratadas como segredo. Elas são deliberadamente não semânticas
# e continuam protegidas por token, origem, store/session e rate limit.
CHECKOUT_TOKEN_PATH = "/_nsv/a646e9ba169dc7f01c5845c5e6019d24"
CHECKOUT_VALIDATE_PATH = "/_nsv/0f6958d6a5d10f3bb4b28ce4c3c302dc"

_ROTULOS_PRIVADOS = {
    "WEBHOOK_PEDIDOS_PATH": "webhook-pedidos-v1",
    "LGPD_STORE_REDACT_PATH": "lgpd-store-redact-v1",
    "LGPD_CUSTOMER_REDACT_PATH": "lgpd-customer-redact-v1",
    "LGPD_CUSTOMER_DATA_PATH": "lgpd-customer-data-v1",
    "HEALTH_PATH": "health-v1",
}


def _segredo_valido() -> str:
    segredo = str(PRIVATE_ROUTE_SECRET or "").strip()
    if len(segredo) < 32:
        raise RuntimeError(
            "PRIVATE_ROUTE_SECRET deve estar configurado com pelo menos 32 caracteres."
        )
    return segredo


def derivar_rota_privada(rotulo: str) -> str:
    """Deriva uma URL estável e não semântica para rotas somente servidor-servidor."""
    segredo = _segredo_valido()
    digest = hmac.new(
        segredo.encode("utf-8"),
        rotulo.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]
    return f"{_PREFIXO}/{digest}"


WEBHOOK_PEDIDOS_PATH = derivar_rota_privada(_ROTULOS_PRIVADOS["WEBHOOK_PEDIDOS_PATH"])
LGPD_STORE_REDACT_PATH = derivar_rota_privada(_ROTULOS_PRIVADOS["LGPD_STORE_REDACT_PATH"])
LGPD_CUSTOMER_REDACT_PATH = derivar_rota_privada(_ROTULOS_PRIVADOS["LGPD_CUSTOMER_REDACT_PATH"])
LGPD_CUSTOMER_DATA_PATH = derivar_rota_privada(_ROTULOS_PRIVADOS["LGPD_CUSTOMER_DATA_PATH"])
HEALTH_PATH = derivar_rota_privada(_ROTULOS_PRIVADOS["HEALTH_PATH"])


def listar_rotas_privadas() -> dict[str, str]:
    return {
        "CHECKOUT_TOKEN_PATH": CHECKOUT_TOKEN_PATH,
        "CHECKOUT_VALIDATE_PATH": CHECKOUT_VALIDATE_PATH,
        "WEBHOOK_PEDIDOS_PATH": WEBHOOK_PEDIDOS_PATH,
        "LGPD_STORE_REDACT_PATH": LGPD_STORE_REDACT_PATH,
        "LGPD_CUSTOMER_REDACT_PATH": LGPD_CUSTOMER_REDACT_PATH,
        "LGPD_CUSTOMER_DATA_PATH": LGPD_CUSTOMER_DATA_PATH,
        "HEALTH_PATH": HEALTH_PATH,
    }


if __name__ == "__main__":
    for nome, caminho in listar_rotas_privadas().items():
        print(f"{nome}={caminho}")
