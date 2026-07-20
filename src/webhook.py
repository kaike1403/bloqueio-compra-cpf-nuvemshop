from typing import Any
import hmac
import logging

from flask import Blueprint, jsonify, request

from src.config import STORE_ID, WEBHOOK_SECRET
from src.processador import processar_pedido


logger = logging.getLogger(__name__)
webhook_bp = Blueprint("webhook", __name__)


def extrair_id_do_evento(dados: dict[str, Any]) -> str:
    pedido_id = dados.get("id")
    return "" if pedido_id is None else str(pedido_id).strip()


@webhook_bp.route("/webhooks/pedidos", methods=["POST"])
def receber_webhook_pedido():
    # A Nuvemshop permite cadastrar cabeçalhos customizados no webhook.
    # O segredo deve ser obrigatório no Render e igual ao cadastrado no webhook.
    if not WEBHOOK_SECRET:
        logger.error("WEBHOOK_SECRET não configurado")
        return jsonify({"sucesso": False, "erro": "Webhook indisponível"}), 503

    logger.info("Headers recebidos: %s", dict(request.headers))

    segredo_recebido = request.headers.get("X-Webhook-Secret", "")

    if not segredo_recebido or not hmac.compare_digest(
        segredo_recebido, WEBHOOK_SECRET
    ):
        logger.warning("Tentativa de webhook não autorizada")
        return jsonify({"sucesso": False, "erro": "Webhook não autorizado"}), 401

    if request.content_length and request.content_length > 16_384:
        return jsonify({"sucesso": False, "erro": "Payload muito grande"}), 413

    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({"sucesso": False, "erro": "JSON inválido"}), 400

    if STORE_ID and str(dados.get("store_id")) != str(STORE_ID):
        logger.warning("Webhook recebido para loja diferente")
        return jsonify({"sucesso": False, "erro": "Loja inválida"}), 403

    evento = str(dados.get("event", "")).strip()
    if evento not in {"order/created", "order/updated"}:
        return jsonify({"sucesso": True, "mensagem": "Evento ignorado"}), 200

    pedido_id = extrair_id_do_evento(dados)
    if not pedido_id:
        return jsonify({"sucesso": False, "erro": "ID do pedido ausente"}), 400

    try:
        resultado = processar_pedido(pedido_id=pedido_id, registrar_no_banco=True)
    except Exception:
        logger.exception("Erro ao processar webhook do pedido %s", pedido_id)
        return jsonify({"sucesso": False, "erro": "Erro interno"}), 500

    # Não devolve detalhes internos do processamento ao chamador.
    return jsonify({
        "sucesso": True,
        "pedido_id": pedido_id,
        "reprocessamento": bool(resultado.get("reprocessamento")),
    }), 200
