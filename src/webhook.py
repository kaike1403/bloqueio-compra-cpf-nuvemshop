from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from src.config import NUVEMSHOP_APP_SECRET, STORE_ID
from src.nuvemshop_webhook_security import (
    assinatura_valida,
    loja_webhook_valida,
    obter_assinatura_webhook,
)
from src.processador import processar_pedido
from src.rate_limit import limiter


logger = logging.getLogger(__name__)
webhook_bp = Blueprint("webhook", __name__)


def extrair_id_do_evento(dados: dict[str, Any]) -> str:
    pedido_id = dados.get("id")
    if pedido_id is None:
        return ""
    return str(pedido_id).strip()


@webhook_bp.route("/webhooks/pedidos", methods=["POST"])
@limiter.limit("120 per minute", methods=["POST"])
def receber_webhook_pedido():
    """Recebe order/created e order/updated somente com HMAC válido."""
    if not NUVEMSHOP_APP_SECRET or not str(STORE_ID or "").strip():
        logger.error("Configuração de segurança do webhook ausente.")
        return jsonify(
            {"sucesso": False, "erro": "Webhook indisponível"}
        ), 503

    if request.content_length and request.content_length > 16_384:
        return jsonify(
            {"sucesso": False, "erro": "Payload inválido"}
        ), 413

    corpo_bruto = request.get_data(cache=True)
    assinatura_recebida = obter_assinatura_webhook()
    assinatura_ok, motivo_assinatura = assinatura_valida(
        corpo_bruto,
        assinatura_recebida,
    )

    if not assinatura_ok:
        logger.warning(
            "Webhook de pedido rejeitado: assinatura inválida (%s).",
            motivo_assinatura,
        )
        return jsonify(
            {"sucesso": False, "erro": "Webhook não autorizado"}
        ), 401

    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify(
            {"sucesso": False, "erro": "Payload inválido"}
        ), 400

    if not loja_webhook_valida(dados.get("store_id")):
        logger.warning("Webhook de pedido rejeitado: store_id divergente.")
        return jsonify(
            {"sucesso": False, "erro": "Webhook não autorizado"}
        ), 403

    evento = str(dados.get("event", "")).strip()
    if evento not in {"order/created", "order/updated"}:
        logger.info("Evento de webhook ignorado: %s", evento or "ausente")
        return jsonify(
            {"sucesso": True, "mensagem": "Evento ignorado"}
        ), 200

    pedido_id = extrair_id_do_evento(dados)
    if not pedido_id:
        # Nunca registra o payload completo: pode conter dados pessoais.
        logger.warning("Webhook de pedido recebido sem ID de pedido.")
        return jsonify(
            {"sucesso": False, "erro": "ID do pedido ausente"}
        ), 400

    logger.info(
        "Processando pedido %s pelo evento %s.",
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
            "Erro interno ao processar webhook do pedido %s.",
            pedido_id,
        )
        return jsonify(
            {"sucesso": False, "erro": "Erro interno"}
        ), 500

    logger.info("Pedido %s processado pelo webhook.", pedido_id)
    return jsonify(
        {
            "sucesso": True,
            "pedido_id": pedido_id,
            "evento": evento,
            "reprocessamento": bool(resultado.get("reprocessamento")),
        }
    ), 200
