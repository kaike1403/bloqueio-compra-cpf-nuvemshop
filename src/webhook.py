from typing import Any
import base64
import hashlib
import hmac
import logging

from flask import Blueprint, jsonify, request

from src.config import NUVEMSHOP_APP_SECRET, STORE_ID
from src.processador import processar_pedido


logger = logging.getLogger(__name__)
webhook_bp = Blueprint("webhook", __name__)


def extrair_id_do_evento(dados: dict[str, Any]) -> str:
    pedido_id = dados.get("id")

    if pedido_id is None:
        return ""

    return str(pedido_id).strip()


def assinatura_valida(
    corpo_bruto: bytes,
    assinatura_recebida: str,
) -> bool:
    """
    Valida a assinatura HMAC-SHA256 enviada pela Nuvemshop.

    A assinatura principal é comparada em Base64.
    Também é mantida uma comparação hexadecimal como compatibilidade.
    """

    segredo = str(NUVEMSHOP_APP_SECRET or "").strip()
    assinatura = str(assinatura_recebida or "").strip()

    if not segredo or not assinatura:
        return False

    digest_bruto = hmac.new(
        segredo.encode("utf-8"),
        corpo_bruto,
        hashlib.sha256,
    ).digest()

    assinatura_base64 = base64.b64encode(
        digest_bruto
    ).decode("utf-8")

    # Comparação principal: Base64
    if hmac.compare_digest(
        assinatura_base64,
        assinatura,
    ):
        return True

    # Compatibilidade caso o provedor envie hexadecimal
    assinatura_hexadecimal = digest_bruto.hex()

    return hmac.compare_digest(
        assinatura_hexadecimal.lower(),
        assinatura.lower(),
    )


@webhook_bp.route(
    "/webhooks/pedidos",
    methods=["POST"],
)
def receber_webhook_pedido():
    if not NUVEMSHOP_APP_SECRET:
        logger.error(
            "NUVEMSHOP_APP_SECRET não configurado"
        )

        return jsonify(
            {
                "sucesso": False,
                "erro": "Webhook indisponível",
            }
        ), 503

    if (
        request.content_length
        and request.content_length > 16_384
    ):
        return jsonify(
            {
                "sucesso": False,
                "erro": "Payload muito grande",
            }
        ), 413

    # É essencial validar o corpo bruto exatamente como recebido.
    corpo_bruto = request.get_data(cache=True)

    assinatura_recebida = request.headers.get(
        "X-Linkedstore-Hmac-Sha256",
        "",
    ).strip()

    logger.info(
        "Webhook recebido: assinatura_presente=%s, "
        "tamanho_payload=%s",
        bool(assinatura_recebida),
        len(corpo_bruto),
    )

    if not assinatura_valida(
        corpo_bruto,
        assinatura_recebida,
    ):
        logger.warning(
            "Assinatura HMAC do webhook inválida. "
            "Tamanho da assinatura recebida: %s",
            len(assinatura_recebida),
        )

        return jsonify(
            {
                "sucesso": False,
                "erro": "Webhook não autorizado",
            }
        ), 401

    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return jsonify(
            {
                "sucesso": False,
                "erro": "JSON inválido",
            }
        ), 400

    store_id_recebido = str(
        dados.get("store_id", "")
    ).strip()

    store_id_configurado = str(
        STORE_ID or ""
    ).strip()

    if (
        store_id_configurado
        and store_id_recebido != store_id_configurado
    ):
        logger.warning(
            "Webhook recebido para loja diferente. "
            "Recebido=%s; configurado=%s",
            store_id_recebido,
            store_id_configurado,
        )

        return jsonify(
            {
                "sucesso": False,
                "erro": "Loja inválida",
            }
        ), 403

    evento = str(
        dados.get("event", "")
    ).strip()

    if evento not in {
        "order/created",
        "order/updated",
    }:
        logger.info(
            "Evento ignorado: %s",
            evento,
        )

        return jsonify(
            {
                "sucesso": True,
                "mensagem": "Evento ignorado",
            }
        ), 200

    pedido_id = extrair_id_do_evento(dados)

    if not pedido_id:
        logger.warning(
            "Webhook sem ID de pedido: %s",
            dados,
        )

        return jsonify(
            {
                "sucesso": False,
                "erro": "ID do pedido ausente",
            }
        ), 400

    logger.info(
        "Processando pedido %s pelo evento %s",
        pedido_id,
        evento,
    )

    try:
        resultado = processar_pedido(
            pedido_id=pedido_id,
            registrar_no_banco=True,
        )

    except Exception:
        logger.exception(
            "Erro ao processar webhook do pedido %s",
            pedido_id,
        )

        return jsonify(
            {
                "sucesso": False,
                "erro": "Erro interno",
            }
        ), 500

    logger.info(
        "Pedido %s processado com sucesso",
        pedido_id,
    )

    return jsonify(
        {
            "sucesso": True,
            "pedido_id": pedido_id,
            "evento": evento,
            "reprocessamento": bool(
                resultado.get("reprocessamento")
            ),
        }
    ), 200