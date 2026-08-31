from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()


STORE_ID = os.getenv("NUVEMSHOP_STORE_ID", "").strip()
ACCESS_TOKEN = os.getenv("NUVEMSHOP_ACCESS_TOKEN", "").strip()
USER_AGENT = os.getenv("NUVEMSHOP_USER_AGENT", "").strip()
NUVEMSHOP_APP_SECRET = os.getenv("NUVEMSHOP_APP_SECRET", "").strip()
PRIVATE_ROUTE_SECRET = os.getenv("PRIVATE_ROUTE_SECRET", "").strip()

API_BASE_URL = "https://api.nuvemshop.com.br/v1"


def _inteiro_env(
    nome: str,
    padrao: int,
    minimo: int,
    maximo: int,
) -> int:
    try:
        valor = int(os.getenv(nome, str(padrao)).strip())
    except (TypeError, ValueError):
        valor = padrao

    return max(minimo, min(maximo, valor))


def _normalizar_caminho_admin(valor: str) -> str:
    caminho = str(valor or "/admin").strip()
    if not caminho.startswith("/"):
        caminho = "/" + caminho

    caminho = caminho.rstrip("/") or "/admin"

    # Evita configuração acidental com query string/fragmento ou travessia.
    if any(caractere in caminho for caractere in ("?", "#", "..")):
        return "/admin"

    return caminho


def validar_configuracoes() -> None:
    variaveis_ausentes = []

    if not STORE_ID:
        variaveis_ausentes.append("NUVEMSHOP_STORE_ID")
    if not ACCESS_TOKEN:
        variaveis_ausentes.append("NUVEMSHOP_ACCESS_TOKEN")
    if not USER_AGENT:
        variaveis_ausentes.append("NUVEMSHOP_USER_AGENT")

    if variaveis_ausentes:
        raise RuntimeError(
            "Variáveis ausentes no ambiente: "
            + ", ".join(variaveis_ausentes)
        )


def obter_headers() -> dict[str, str]:
    validar_configuracoes()

    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def obter_url(endpoint: str) -> str:
    validar_configuracoes()

    endpoint = endpoint.strip()
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    return f"{API_BASE_URL}/{STORE_ID}{endpoint}"


CANCELAMENTO_REAL_ATIVO = (
    os.getenv("CANCELAMENTO_REAL_ATIVO", "false").strip().lower() == "true"
)
CANCELAMENTO_NOTIFICAR_CLIENTE = (
    os.getenv("CANCELAMENTO_NOTIFICAR_CLIENTE", "true").strip().lower()
    == "true"
)
CANCELAMENTO_REPOR_ESTOQUE = (
    os.getenv("CANCELAMENTO_REPOR_ESTOQUE", "true").strip().lower() == "true"
)
MODO_AUTOMATICO = (
    os.getenv("MODO_AUTOMATICO", "false").strip().lower() == "true"
)


CORS_ORIGINS = [
    origem.strip()
    for origem in os.getenv(
        "CORS_ORIGINS",
        "https://gdlp.com.br,https://www.gdlp.com.br",
    ).split(",")
    if origem.strip()
]

CHECKOUT_TOKEN_SECRET = os.getenv("CHECKOUT_TOKEN_SECRET", "").strip()
CHECKOUT_TOKEN_TTL_SECONDS = _inteiro_env(
    "CHECKOUT_TOKEN_TTL_SECONDS",
    padrao=300,
    minimo=60,
    maximo=900,
)

LGPD_RETENCAO_DIAS = _inteiro_env(
    "LGPD_RETENCAO_DIAS",
    padrao=180,
    minimo=1,
    maximo=3650,
)

RATELIMIT_STORAGE_URI = (
    os.getenv("RATELIMIT_STORAGE_URI", "").strip() or "memory://"
)

# O caminho customizável reduz ruído de scanners, mas NÃO substitui
# autenticação, rate limit ou uma camada externa como Cloudflare Access/VPN.
ADMIN_PATH = _normalizar_caminho_admin(
    os.getenv("ADMIN_PATH", "/admin")
)
