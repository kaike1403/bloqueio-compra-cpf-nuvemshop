from typing import Any

from src.banco import conectar, criar_banco


def criar_tabela_produtos_controlados() -> None:
    """
    Cria a tabela dos produtos que possuem limite por CPF.
    """

    criar_banco()

    with conectar() as conexao:
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS produtos_controlados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id TEXT NOT NULL UNIQUE,
                nome_produto TEXT,
                limite_por_cpf INTEGER NOT NULL DEFAULT 1,
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conexao.commit()


def adicionar_produto_controlado(
    produto_id: int | str,
    nome_produto: str = "",
    limite_por_cpf: int = 1,
) -> bool:
    """
    Adiciona ou atualiza um produto controlado.
    """

    criar_tabela_produtos_controlados()

    produto_id_texto = str(produto_id).strip()

    if not produto_id_texto:
        raise ValueError("produto_id inválido.")

    if limite_por_cpf < 1:
        raise ValueError(
            "O limite por CPF deve ser maior ou igual a 1."
        )

    with conectar() as conexao:
        conexao.execute(
            """
            INSERT INTO produtos_controlados (
                produto_id,
                nome_produto,
                limite_por_cpf,
                ativo
            )
            VALUES (?, ?, ?, 1)

            ON CONFLICT(produto_id)
            DO UPDATE SET
                nome_produto = excluded.nome_produto,
                limite_por_cpf = excluded.limite_por_cpf,
                ativo = 1
            """,
            (
                produto_id_texto,
                nome_produto,
                limite_por_cpf,
            ),
        )

        conexao.commit()

    return True


def produto_esta_controlado(
    produto_id: int | str,
) -> bool:
    """
    Verifica se o produto está ativo na lista de controle.
    """

    criar_tabela_produtos_controlados()

    with conectar() as conexao:
        resultado = conexao.execute(
            """
            SELECT 1
            FROM produtos_controlados
            WHERE produto_id = ?
              AND ativo = 1
            LIMIT 1
            """,
            (str(produto_id),),
        ).fetchone()

    return resultado is not None


def obter_configuracao_produto(
    produto_id: int | str,
) -> dict[str, Any]:
    """
    Retorna as configurações do produto controlado.
    """

    criar_tabela_produtos_controlados()

    with conectar() as conexao:
        resultado = conexao.execute(
            """
            SELECT *
            FROM produtos_controlados
            WHERE produto_id = ?
            LIMIT 1
            """,
            (str(produto_id),),
        ).fetchone()

    if resultado is None:
        return {}

    return dict(resultado)


def desativar_produto_controlado(
    produto_id: int | str,
) -> bool:
    """
    Desativa o controle sem apagar o histórico.
    """

    criar_tabela_produtos_controlados()

    with conectar() as conexao:
        cursor = conexao.execute(
            """
            UPDATE produtos_controlados
            SET ativo = 0
            WHERE produto_id = ?
            """,
            (str(produto_id),),
        )

        conexao.commit()

    return cursor.rowcount > 0


def listar_produtos_controlados(
    somente_ativos: bool = True,
) -> list[dict[str, Any]]:
    """
    Lista os produtos configurados.
    """

    criar_tabela_produtos_controlados()

    consulta = """
        SELECT *
        FROM produtos_controlados
    """

    if somente_ativos:
        consulta += " WHERE ativo = 1"

    consulta += " ORDER BY criado_em DESC"

    with conectar() as conexao:
        resultados = conexao.execute(
            consulta
        ).fetchall()

    return [dict(linha) for linha in resultados]


def teste() -> None:
    criar_tabela_produtos_controlados()

    adicionar_produto_controlado(
        produto_id=352087421,
        nome_produto=(
            "BONÉ NEW ERA 950 RETRO CROWN "
            "NEW YORK YANKEES"
        ),
        limite_por_cpf=1,
    )

    print(
        "Produto controlado:",
        produto_esta_controlado(352087421),
    )

    print("\nProdutos ativos:")

    for produto in listar_produtos_controlados():
        print(produto)


if __name__ == "__main__":
    teste()