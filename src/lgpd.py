from typing import Any

from flask import Blueprint, jsonify, request

from src.banco import conectar, criar_banco, normalizar_cpf


lgpd_bp = Blueprint(
    "lgpd",
    __name__,
)


def obter_payload() -> dict[str, Any] | None:
    """
    Retorna o JSON recebido ou None quando o corpo for inválido.
    """

    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return None

    return dados


def extrair_cpf(dados: dict[str, Any]) -> str:
    """
    Tenta localizar o CPF em formatos diferentes de payload.
    """

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

        if len(cpf) == 11:
            return cpf

    return ""


def remover_dados_do_cpf(cpf: str) -> dict[str, int]:
    """
    Remove ou anonimiza registros relacionados ao CPF.

    Compras e cancelamentos são apagados.
    Logs são anonimizados para preservar histórico técnico
    sem manter o dado pessoal.
    """

    criar_banco()

    with conectar() as conexao:
        compras = conexao.execute(
            """
            DELETE FROM compras
            WHERE cpf = ?
            """,
            (cpf,),
        ).rowcount

        cancelamentos = conexao.execute(
            """
            DELETE FROM cancelamentos
            WHERE cpf = ?
            """,
            (cpf,),
        ).rowcount

        logs = conexao.execute(
            """
            UPDATE logs_processamento
            SET cpf = NULL
            WHERE cpf = ?
            """,
            (cpf,),
        ).rowcount

        conexao.commit()

    return {
        "compras_removidas": compras,
        "cancelamentos_removidos": cancelamentos,
        "logs_anonimizados": logs,
    }


@lgpd_bp.route(
    "/webhooks/lgpd/store-redact",
    methods=["POST"],
)
def store_redact():
    """
    Solicitação de exclusão dos dados de uma loja.

    Como seu sistema atualmente trabalha com uma única loja,
    removemos todos os registros pessoais armazenados.
    """

    dados = obter_payload()

    if dados is None:
        return jsonify(
            {
                "success": False,
                "error": "JSON inválido",
            }
        ), 400

    criar_banco()

    with conectar() as conexao:
        total_compras = conexao.execute(
            "DELETE FROM compras"
        ).rowcount

        total_cancelamentos = conexao.execute(
            "DELETE FROM cancelamentos"
        ).rowcount

        total_logs = conexao.execute(
            """
            UPDATE logs_processamento
            SET cpf = NULL
            WHERE cpf IS NOT NULL
            """
        ).rowcount

        conexao.commit()

    return jsonify(
        {
            "success": True,
            "message": "Dados pessoais da loja removidos",
            "result": {
                "compras_removidas": total_compras,
                "cancelamentos_removidos": total_cancelamentos,
                "logs_anonimizados": total_logs,
            },
        }
    ), 200


@lgpd_bp.route(
    "/webhooks/lgpd/customer-redact",
    methods=["POST"],
)
def customer_redact():
    """
    Solicitação de exclusão dos dados de um cliente.
    """

    dados = obter_payload()

    if dados is None:
        return jsonify(
            {
                "success": False,
                "error": "JSON inválido",
            }
        ), 400

    cpf = extrair_cpf(dados)

    if not cpf:
        # Responde 200 para confirmar o recebimento,
        # mas não executa exclusão sem identificador seguro.
        return jsonify(
            {
                "success": True,
                "message": (
                    "Solicitação recebida, mas nenhum CPF "
                    "foi localizado no payload"
                ),
            }
        ), 200

    resultado = remover_dados_do_cpf(cpf)

    return jsonify(
        {
            "success": True,
            "message": "Dados do cliente removidos",
            "result": resultado,
        }
    ), 200


@lgpd_bp.route(
    "/webhooks/lgpd/customer-data-request",
    methods=["POST"],
)
def customer_data_request():
    """
    Solicitação de acesso aos dados armazenados sobre um cliente.

    Por segurança, não devolvemos os dados pessoais diretamente
    na resposta do webhook. Apenas confirmamos o recebimento.
    """

    dados = obter_payload()

    if dados is None:
        return jsonify(
            {
                "success": False,
                "error": "JSON inválido",
            }
        ), 400

    cpf = extrair_cpf(dados)

    quantidade_compras = 0
    quantidade_cancelamentos = 0

    if cpf:
        criar_banco()

        with conectar() as conexao:
            quantidade_compras = conexao.execute(
                """
                SELECT COUNT(*) AS total
                FROM compras
                WHERE cpf = ?
                """,
                (cpf,),
            ).fetchone()["total"]

            quantidade_cancelamentos = conexao.execute(
                """
                SELECT COUNT(*) AS total
                FROM cancelamentos
                WHERE cpf = ?
                """,
                (cpf,),
            ).fetchone()["total"]

    return jsonify(
        {
            "success": True,
            "message": "Solicitação de dados recebida",
            "data_found": bool(
                quantidade_compras
                or quantidade_cancelamentos
            ),
        }
    ), 200