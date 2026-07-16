import os

from dotenv import load_dotenv


# Carrega o arquivo .env da pasta do projeto
load_dotenv()


STORE_ID = os.getenv("NUVEMSHOP_STORE_ID")
ACCESS_TOKEN = os.getenv("NUVEMSHOP_ACCESS_TOKEN")
USER_AGENT = os.getenv("NUVEMSHOP_USER_AGENT")

API_BASE_URL = "https://api.nuvemshop.com.br/v1"


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
            "Variáveis ausentes no arquivo .env: "
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
    os.getenv(
        "CANCELAMENTO_REAL_ATIVO",
        "false",
    ).lower().strip() == "true"
)

CANCELAMENTO_NOTIFICAR_CLIENTE = (
    os.getenv(
        "CANCELAMENTO_NOTIFICAR_CLIENTE",
        "true",
    ).lower().strip() == "true"
)

CANCELAMENTO_REPOR_ESTOQUE = (
    os.getenv(
        "CANCELAMENTO_REPOR_ESTOQUE",
        "true",
    ).lower().strip() == "true"
)

MODO_AUTOMATICO = (
    os.getenv(
        "MODO_AUTOMATICO",
        "false",
    ).strip().lower() == "true"
)