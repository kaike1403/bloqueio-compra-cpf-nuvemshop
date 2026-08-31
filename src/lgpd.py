from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from src.banco import conectar, criar_banco, normalizar_cpf
from src.config import NUVEMSHOP_APP_SECRET, STORE_ID
from src.nuvemshop_webhook_security import (
    assinatura_valida,
    loja_webhook_valida,
    obter_assinatura_webhook,
)
from src.rate_limit import limiter
from src.verificacao import mascarar_cpf, validar_cpf


logger = logging.getLogger(__name__)
lgpd_bp = Blueprint("lgpd", __name__)


class WebhookLgpdInvalido(Exception):
    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


def _validar_webhook_lgpd() -> dict[str, Any]:
    """Valida configuração, tamanho, HMAC, JSON e loja antes de agir."""
    if not NUVEMSHOP_APP_SECRET or not str(STORE_ID or "").strip():
        logger.error("Configuração de segurança dos webhooks LGPD ausente.")
        raise WebhookLgpdInvalido(503, "Webhook indisponível")

    if request.content_length and request.content_length > 16_384:
        raise WebhookLgpdInvalido(413, "Payload inválido")

    corpo_bruto = request.get_data(cache=True)
    assinatura = obter_assinatura_webhook()
    assinatura_ok, motivo = assinatura_valida(corpo_bruto, assinatura)

    if not assinatura_ok:
        logger.warning(
            "Webhook LGPD rejeitado: assinatura inválida (%s).",
            motivo,
        )
        raise WebhookLgpdInvalido(401, "Webhook não autorizado")

    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        raise WebhookLgpdInvalido(400, "Payload inválido")

    if not loja_webhook_valida(dados.get("store_id")):
        logger.warning("Webhook LGPD rejeitado: store_id divergente.")
        raise WebhookLgpdInvalido(403, "Webhook não autorizado")

    return dados


def _resposta_erro(erro: WebhookLgpdInvalido):
    return jsonify({"success": False, "error": erro.mensagem}), erro.status


def extrair_cpf(dados: dict[str, Any]) -> str:
    """Localiza um CPF válido em formatos conhecidos de payload."""
    candidatos = [
        dados.get("cpf"),
        dados.get("document"),
        dados.get("identification"),
        dados.get("customer_document"),
    ]

    cliente = dados.get("customer")
    if isinstance(cliente, dict):
        candidatos.extend(
            [
                cliente.get("cpf"),
                cliente.get("document"),
                cliente.get("identification"),
            ]
        )

    for valor in candidatos:
        cpf = normalizar_cpf(valor)
        if validar_cpf(cpf):
            return cpf

    return ""


def remover_dados_do_cpf(cpf: str) -> dict[str, int]:
    """Remove dados operacionais e anonimiza logs ligados ao CPF."""
    criar_banco()
    cpf_mascarado = mascarar_cpf(cpf)

    with conectar() as conexao:
        compras = conexao.execute(
            "DELETE FROM compras WHERE cpf = ?",
            (cpf,),
        ).rowcount

        cancelamentos = conexao.execute(
            "DELETE FROM cancelamentos WHERE cpf = ?",
            (cpf,),
        ).rowcount

        logs = conexao.execute(
            """
            UPDATE logs_processamento
            SET cpf = NULL
            WHERE cpf = ? OR cpf = ?
            """,
            (cpf, cpf_mascarado),
        ).rowcount

        conexao.commit()

    return {
        "compras_removidas": max(compras, 0),
        "cancelamentos_removidos": max(cancelamentos, 0),
        "logs_anonimizados": max(logs, 0),
    }


@lgpd_bp.route("/webhooks/lgpd/store-redact", methods=["POST"])
@limiter.limit("60 per minute", methods=["POST"])
def store_redact():
    """Exclusão da loja: só executa após HMAC e store_id válidos."""
    try:
        _validar_webhook_lgpd()
    except WebhookLgpdInvalido as erro:
        return _resposta_erro(erro)

    criar_banco()

    with conectar() as conexao:
        total_compras = conexao.execute("DELETE FROM compras").rowcount
        total_cancelamentos = conexao.execute("DELETE FROM cancelamentos").rowcount
        total_logs = conexao.execute(
            """
            UPDATE logs_processamento
            SET cpf = NULL
            WHERE cpf IS NOT NULL
            """
        ).rowcount
        conexao.commit()

    logger.info("Webhook LGPD store-redact processado com sucesso.")
    return jsonify(
        {
            "success": True,
            "result": {
                "compras_removidas": max(total_compras, 0),
                "cancelamentos_removidos": max(total_cancelamentos, 0),
                "logs_anonimizados": max(total_logs, 0),
            },
        }
    ), 200


@lgpd_bp.route("/webhooks/lgpd/customer-redact", methods=["POST"])
@limiter.limit("60 per minute", methods=["POST"])
def customer_redact():
    """Exclusão de cliente autenticada pelo HMAC da Nuvemshop."""
    try:
        dados = _validar_webhook_lgpd()
    except WebhookLgpdInvalido as erro:
        return _resposta_erro(erro)

    cpf = extrair_cpf(dados)
    if cpf:
        remover_dados_do_cpf(cpf)

    # Resposta deliberadamente uniforme: não revela existência do CPF.
    logger.info("Webhook LGPD customer-redact processado.")
    return jsonify({"success": True}), 200


@lgpd_bp.route("/webhooks/lgpd/customer-data-request", methods=["POST"])
@limiter.limit("60 per minute", methods=["POST"])
def customer_data_request():
    """Confirma solicitação LGPD sem atuar como oráculo de existência."""
    try:
        _validar_webhook_lgpd()
    except WebhookLgpdInvalido as erro:
        return _resposta_erro(erro)

    # Não devolve data_found, CPF, contagens ou registros pessoais.
    logger.info("Webhook LGPD customer-data-request recebido.")
    return jsonify({"success": True}), 200
