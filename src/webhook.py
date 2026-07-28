from typing import Any
import base64
import hashlib
import hmac
import logging

from flask import Blueprint, jsonify, request

from src.config import (
    NUVEMSHOP_APP_SECRET,
    STORE_ID,
    WEBHOOK_SECRET,
)
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
) -> tuple[bool, str]:
    """
    Valida HMAC-SHA256 usando os segredos configurados.

    Aceita assinatura em hexadecimal ou Base64.
    Nunca registra o valor dos segredos nos logs.
    """

    assinatura = str(
        assinatura_recebida or ""
    ).strip()

    if not assinatura:
        return False, "assinatura_ausente"

    segredos = [
        (
            "NUVEMSHOP_APP_SECRET",
            str(NUVEMSHOP_APP_SECRET or "").strip(),
        ),
        (
            "WEBHOOK_SECRET",
            str(WEBHOOK_SECRET or "").strip(),
        ),
    ]

    segredos_testados: set[str] = set()

    for nome_variavel, segredo in segredos:
        if not segredo:
            continue

        # Evita testar duas vezes quando as variáveis possuem
        # exatamente o mesmo valor.
        if segredo in segredos_testados:
            continue

        segredos_testados.add(segredo)

        digest_bruto = hmac.new(
            segredo.encode("utf-8"),
            corpo_bruto,
            hashlib.sha256,
        ).digest()

        assinatura_base64 = base64.b64encode(
            digest_bruto
        ).decode("utf-8")

        assinatura_hexadecimal = digest_bruto.hex()

        if hmac.compare_digest(
            assinatura,
            assinatura_base64,
        ):
            return True, nome_variavel + "_base64"

        if hmac.compare_digest(
            assinatura.lower(),
            assinatura_hexadecimal.lower(),
        ):
            return True, nome_variavel + "_hex"

    return False, "nenhum_segredo_correspondeu"


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

    assinatura_recebida = (
        request.headers.get(
            "X-Linkedstore-Hmac-Sha256",
            "",
        )
        or request.headers.get(
            "X-Tiendanube-Hmac-Sha256",
            "",
        )
        or request.headers.get(
            "X-Nuvemshop-Hmac-Sha256",
            "",
        )
    ).strip()

    logger.info(
        "Webhook recebido: assinatura_presente=%s, "
        "tamanho_payload=%s",
        bool(assinatura_recebida),
        len(corpo_bruto),
    )

    assinatura_ok, metodo_assinatura = assinatura_valida(
        corpo_bruto,
        assinatura_recebida,
    )

    if not assinatura_ok:
        logger.warning(
            "Assinatura HMAC inválida. "
            "Tamanho=%s; motivo=%s; "
            "app_secret_configurado=%s; "
            "webhook_secret_configurado=%s",
            len(assinatura_recebida),
            metodo_assinatura,
            bool(NUVEMSHOP_APP_SECRET),
            bool(WEBHOOK_SECRET),
        )

        return jsonify(
            {
                "sucesso": False,
                "erro": "Webhook não autorizado",
            }
        ), 401

    logger.info(
        "Assinatura HMAC válida usando %s",
        metodo_assinatura,
    )

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