from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from src.cancelamento import (
    cancelar_pedido_nuvemshop,
    resposta_para_texto,
)


from src.banco import (
    atualizar_status_cancelamento,
    conectar,
    contar_cancelamentos_pendentes,
    listar_cancelamentos,
    listar_logs,
    normalizar_cpf,
    obter_cancelamento,
)
from src.produtos_controlados import (
    adicionar_produto_controlado,
    criar_tabela_produtos_controlados,
    desativar_produto_controlado,
    listar_produtos_controlados,
)


from src.seguranca import proteger_admin


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
)


@admin_bp.before_request
def exigir_autenticacao_admin():
    return proteger_admin()


def listar_compras_com_filtro(
    pesquisa: str = "",
) -> list[dict]:
    """
    Lista as compras registradas.

    A pesquisa pode localizar:
    - CPF;
    - nome do produto;
    - product_id;
    - SKU;
    - número do pedido.
    """

    pesquisa = pesquisa.strip()

    consulta = """
        SELECT *
        FROM compras
    """

    parametros: tuple = ()

    if pesquisa:
        cpf_pesquisa = normalizar_cpf(pesquisa)

        termo = f"%{pesquisa}%"
        termo_cpf = f"%{cpf_pesquisa}%"

        consulta += """
            WHERE cpf LIKE ?
               OR nome_produto LIKE ?
               OR produto_id LIKE ?
               OR sku LIKE ?
               OR numero_pedido LIKE ?
        """

        parametros = (
            termo_cpf,
            termo,
            termo,
            termo,
            termo,
        )

    consulta += """
        ORDER BY criado_em DESC
        LIMIT 500
    """

    with conectar() as conexao:
        resultados = conexao.execute(
            consulta,
            parametros,
        ).fetchall()

    return [dict(linha) for linha in resultados]


@admin_bp.route("/", methods=["GET"])
def painel():
    """
    Página inicial do painel administrativo.
    """

    criar_tabela_produtos_controlados()

    pesquisa = request.args.get(
        "pesquisa",
        "",
    ).strip()

    produtos = listar_produtos_controlados(
        somente_ativos=False,
    )

    compras = listar_compras_com_filtro(
        pesquisa=pesquisa,
    )
    logs = listar_logs(500)

    cancelamentos = listar_cancelamentos()
    total_cancelamentos_pendentes = contar_cancelamentos_pendentes()

    total_produtos_ativos = sum(
        1
        for produto in produtos
        if produto.get("ativo") == 1
    )

    return render_template(
        "admin.html",
        produtos=produtos,
        cancelamentos=cancelamentos,
        total_cancelamentos_pendentes=total_cancelamentos_pendentes,
        compras=compras,
        pesquisa=pesquisa,
        total_produtos=len(produtos),
        total_produtos_ativos=total_produtos_ativos,
        total_compras=len(compras),
        logs=logs,
    )


@admin_bp.route(
    "/produtos/adicionar",
    methods=["POST"],
)
def adicionar_produto():
    """
    Adiciona ou reativa um produto controlado.
    """

    produto_id = request.form.get(
        "produto_id",
        "",
    ).strip()

    nome_produto = request.form.get(
        "nome_produto",
        "",
    ).strip()

    limite_texto = request.form.get(
        "limite_por_cpf",
        "1",
    ).strip()

    if not produto_id:
        flash(
            "Informe o ID do produto.",
            "erro",
        )

        return redirect(
            url_for("admin.painel")
        )

    try:
        limite_por_cpf = int(limite_texto)

        adicionar_produto_controlado(
            produto_id=produto_id,
            nome_produto=nome_produto,
            limite_por_cpf=limite_por_cpf,
        )

    except ValueError as erro:
        flash(
            str(erro),
            "erro",
        )

        return redirect(
            url_for("admin.painel")
        )

    flash(
        "Produto adicionado ao controle.",
        "sucesso",
    )

    return redirect(
        url_for("admin.painel")
    )


@admin_bp.route(
    "/produtos/<produto_id>/desativar",
    methods=["POST"],
)
def desativar_produto(produto_id: str):
    """
    Desativa um produto sem apagar seu histórico.
    """

    desativado = desativar_produto_controlado(
        produto_id
    )

    if desativado:
        flash(
            "Produto desativado.",
            "sucesso",
        )
    else:
        flash(
            "Produto não localizado.",
            "erro",
        )

    return redirect(
        url_for("admin.painel")
    )


@admin_bp.route(
    "/produtos/<produto_id>/ativar",
    methods=["POST"],
)
def ativar_produto(produto_id: str):
    """
    Reativa um produto controlado já existente.
    """

    criar_tabela_produtos_controlados()

    with conectar() as conexao:
        cursor = conexao.execute(
            """
            UPDATE produtos_controlados
            SET ativo = 1
            WHERE produto_id = ?
            """,
            (produto_id,),
        )

        conexao.commit()

    if cursor.rowcount:
        flash(
            "Produto ativado.",
            "sucesso",
        )
    else:
        flash(
            "Produto não localizado.",
            "erro",
        )

    return redirect(
        url_for("admin.painel")
    )
@admin_bp.route(
    "/cancelamentos/<int:cancelamento_id>/cancelar",
    methods=["POST"],
)
def executar_cancelamento(cancelamento_id: int):
    cancelamento = obter_cancelamento(
        cancelamento_id
    )

    if not cancelamento:
        flash(
            "Cancelamento não localizado.",
            "erro",
        )

        return redirect(
            url_for("admin.painel")
        )

    if cancelamento.get("status") != "pendente":
        flash(
            "Esse cancelamento já foi processado.",
            "erro",
        )

        return redirect(
            url_for("admin.painel")
        )

    resultado = cancelar_pedido_nuvemshop(
        pedido_id=cancelamento["pedido_id"],
        motivo="other",
    )

    resposta_texto = resposta_para_texto(
        resultado
    )

    if resultado.get("simulado"):
        novo_status = "simulado"

        mensagem = (
            "Cancelamento simulado. "
            "Nenhuma alteração foi feita na Nuvemshop."
        )

        categoria = "sucesso"

    elif resultado.get("cancelado"):
        novo_status = "cancelado"

        mensagem = (
            f"Pedido #{cancelamento.get('numero_pedido')} "
            "cancelado na Nuvemshop."
        )

        categoria = "sucesso"

    else:
        novo_status = "erro"

        mensagem = (
            "A Nuvemshop não confirmou o cancelamento."
        )

        categoria = "erro"

    atualizar_status_cancelamento(
        cancelamento_id=cancelamento_id,
        status=novo_status,
        resposta_api=resposta_texto,
    )

    flash(
        mensagem,
        categoria,
    )

    return redirect(
        url_for("admin.painel")
    )

@admin_bp.route(
    "/cancelamentos/<int:cancelamento_id>/liberar",
    methods=["POST"],
)
def liberar_cancelamento(cancelamento_id: int):
    cancelamento = obter_cancelamento(cancelamento_id)

    if not cancelamento:
        flash("Cancelamento não localizado.", "erro")
        return redirect(url_for("admin.painel"))

    if cancelamento.get("status") != "pendente":
        flash(
            "Esse cancelamento já foi processado.",
            "erro",
        )
        return redirect(url_for("admin.painel"))

    atualizado = atualizar_status_cancelamento(
        cancelamento_id=cancelamento_id,
        status="liberado",
        resposta_api="Pedido liberado manualmente pelo painel.",
    )

    if atualizado:
        flash(
            f"Pedido #{cancelamento.get('numero_pedido')} liberado.",
            "sucesso",
        )
    else:
        flash("Não foi possível liberar o pedido.", "erro")

    return redirect(url_for("admin.painel"))