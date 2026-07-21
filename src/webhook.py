from typing import Any
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
    return "" if pedido_id is None else str(pedido_id).strip()


def assinatura_valida(
    corpo_bruto: bytes,
    assinatura_recebida: str,
) -> bool:
    if not NUVEMSHOP_APP_SECRET or not assinatura_recebida:
        return False

    assinatura_calculada = hmac.new(
        NUVEMSHOP_APP_SECRET.encode("utf-8"),
        corpo_bruto,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        assinatura_calculada.lower(),
        assinatura_recebida.strip().lower(),
    )


@webhook_bp.route("/webhooks/pedidos", methods=["POST"])
def receber_webhook_pedido():

    if not NUVEMSHOP_APP_SECRET:
        logger.error("NUVEMSHOP_APP_SECRET não configurado")
        return jsonify(
            {
                "sucesso": False,
                "erro": "Webhook indisponível",
            }
        ), 503


    if request.content_length and request.content_length > 16_384:
        return jsonify(
            {
                "sucesso": False,
                "erro": "Payload muito grande",
            }
        ), 413

    corpo_bruto = request.get_data(cache=True)

    assinatura_recebida = request.headers.get(
        "x-linkedstore-hmac-sha256",
        "",
    )

    if not assinatura_valida(corpo_bruto, assinatura_recebida):
        logger.warning("Assinatura HMAC do webhook inválida")
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

    if STORE_ID and str(dados.get("store_id")) != str(STORE_ID):
        logger.warning("Webhook recebido para loja diferente")
        return jsonify(
            {
                "sucesso": False,
                "erro": "Loja inválida",
            }
        ), 403

    evento = str(dados.get("event", "")).strip()

    if evento not in {"order/created", "order/updated"}:
        return jsonify(
            {
                "sucesso": True,
                "mensagem": "Evento ignorado",
            }
        ), 200

    pedido_id = extrair_id_do_evento(dados)

    if not pedido_id:
        return jsonify(
            {
                "sucesso": False,
                "erro": "ID do pedido ausente",
            }
        ), 400

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

    return jsonify(
        {
            "sucesso": True,
            "pedido_id": pedido_id,
            "reprocessamento": bool(
                resultado.get("reprocessamento")
            ),
        }
    ), 200