import json
from typing import Any

from src.config import (
    CANCELAMENTO_NOTIFICAR_CLIENTE,
    CANCELAMENTO_REAL_ATIVO,
    CANCELAMENTO_REPOR_ESTOQUE,
)
from src.nuvemshop import fazer_requisicao


def cancelar_pedido_nuvemshop(
    pedido_id: int | str,
    motivo: str = "other",
) -> dict[str, Any]:
    """
    Cancela um pedido na Nuvemshop.

    Enquanto CANCELAMENTO_REAL_ATIVO=false,
    nenhuma requisição de cancelamento é enviada.
    """

    motivos_permitidos = {
        "customer",
        "inventory",
        "fraud",
        "other",
    }

    if motivo not in motivos_permitidos:
        motivo = "other"

    resultado: dict[str, Any] = {
        "sucesso": False,
        "cancelado": False,
        "simulado": not CANCELAMENTO_REAL_ATIVO,
        "pedido_id": str(pedido_id),
        "motivo": motivo,
        "resposta": None,
    }

    if not CANCELAMENTO_REAL_ATIVO:
        mensagem = (
            "Cancelamento real desativado no .env. "
            "Nenhuma alteração foi feita na Nuvemshop."
        )

        print(mensagem)

        resultado["sucesso"] = True
        resultado["resposta"] = mensagem

        return resultado

    dados = {
        "reason": motivo,
        "email": CANCELAMENTO_NOTIFICAR_CLIENTE,
        "restock": CANCELAMENTO_REPOR_ESTOQUE,
    }

    resposta = fazer_requisicao(
        metodo="POST",
        endpoint=f"/orders/{pedido_id}/cancel",
        dados=dados,
    )

    if not isinstance(resposta, dict):
        resultado["resposta"] = (
            "A API não retornou uma resposta válida."
        )

        return resultado

    status_pedido = str(
        resposta.get("status", "")
    ).lower().strip()

    cancelado = status_pedido == "cancelled"

    resultado["sucesso"] = cancelado
    resultado["cancelado"] = cancelado
    resultado["resposta"] = resposta

    return resultado


def resposta_para_texto(
    resultado: dict[str, Any],
) -> str:
    """
    Converte o retorno do cancelamento para armazenamento no SQLite.
    """

    try:
        return json.dumps(
            resultado,
            ensure_ascii=False,
            default=str,
        )

    except TypeError:
        return str(resultado)