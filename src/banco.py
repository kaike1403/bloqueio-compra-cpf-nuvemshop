import sqlite3
from pathlib import Path
from typing import Any



PASTA_RAIZ = Path(__file__).resolve().parent.parent
PASTA_BANCO = PASTA_RAIZ / "banco"
PASTA_BANCO.mkdir(parents=True, exist_ok=True)

CAMINHO_BANCO = PASTA_BANCO / "compras.db"

def listar_logs(
    limite: int = 500,
) -> list[dict[str, Any]]:
    """
    Retorna os logs mais recentes.
    """

    with conectar() as conexao:
        resultados = conexao.execute(
            """
            SELECT *
            FROM logs_processamento
            ORDER BY criado_em DESC, id DESC
            LIMIT ?
            """,
            (limite,),
        ).fetchall()

    return [dict(linha) for linha in resultados]

def registrar_log(
    resultado: str,
    motivo: str = "",
    pedido_id: int | str | None = None,
    numero_pedido: int | str | None = None,
    cpf: str | None = None,
    produto_id: int | str | None = None,
    variante_id: int | str | None = None,
    sku: str | None = None,
    nome_produto: str | None = None,
) -> None:
    """
    Registra uma decisão tomada pelo processador.
    """

    criar_banco()

    cpf_limpo = normalizar_cpf(cpf)

    with conectar() as conexao:
        conexao.execute(
            """
            INSERT INTO logs_processamento (
                pedido_id,
                numero_pedido,
                cpf,
                produto_id,
                variante_id,
                sku,
                nome_produto,
                resultado,
                motivo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(pedido_id) if pedido_id is not None else None,
                str(numero_pedido) if numero_pedido is not None else None,
                cpf_limpo or None,
                str(produto_id) if produto_id is not None else None,
                str(variante_id) if variante_id is not None else None,
                sku,
                nome_produto,
                resultado,
                motivo,
            ),
        )
        
def conectar() -> sqlite3.Connection:
    """
    Abre uma conexão com o banco SQLite.

    row_factory permite acessar os dados pelo nome das colunas.
    Exemplo:
        linha["cpf"]
    """

    conexao = sqlite3.connect(CAMINHO_BANCO)
    conexao.row_factory = sqlite3.Row

    return conexao
def registrar_cancelamento_pendente(
    pedido_id: int | str,
    numero_pedido: int | str | None,
    cpf: str,
    produto_id: int | str,
    variante_id: int | str | None = None,
    sku: str | None = None,
    nome_produto: str | None = None,
    motivo: str = "Compra duplicada para o mesmo CPF",
) -> bool:
    """
    Adiciona um pedido à fila de cancelamentos.

    Retorna:
        True  -> cancelamento pendente criado
        False -> já existia para esse pedido e produto
    """

    criar_banco()

    cpf_limpo = normalizar_cpf(cpf)

    try:
        with conectar() as conexao:
            conexao.execute(
                """
                INSERT INTO cancelamentos (
                    pedido_id,
                    numero_pedido,
                    cpf,
                    produto_id,
                    variante_id,
                    sku,
                    nome_produto,
                    motivo,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendente')
                """,
                (
                    str(pedido_id),
                    (
                        str(numero_pedido)
                        if numero_pedido is not None
                        else None
                    ),
                    cpf_limpo or None,
                    str(produto_id),
                    (
                        str(variante_id)
                        if variante_id is not None
                        else None
                    ),
                    sku,
                    nome_produto,
                    motivo,
                ),
            )

            conexao.commit()

        return True

    except sqlite3.IntegrityError:
        return False
    
def atualizar_cancelamentos_do_pedido(
    pedido_id: int | str,
    status: str,
    resposta_api: str | None = None,
) -> int:
    """
    Atualiza todos os registros de cancelamento
    relacionados ao mesmo pedido.
    """

    status_permitidos = {
        "pendente",
        "simulado",
        "cancelado",
        "liberado",
        "erro",
    }

    if status not in status_permitidos:
        raise ValueError(
            f"Status de cancelamento inválido: {status}"
        )

    with conectar() as conexao:
        cursor = conexao.execute(
            """
            UPDATE cancelamentos
            SET
                status = ?,
                resposta_api = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE pedido_id = ?
            """,
            (
                status,
                resposta_api,
                str(pedido_id),
            ),
        )

        conexao.commit()

    return cursor.rowcount

def listar_cancelamentos(
    status: str | None = None,
    limite: int = 500,
) -> list[dict[str, Any]]:
    """
    Lista os cancelamentos mais recentes.

    Exemplos de status:
        pendente
        cancelado
        liberado
        erro
    """

    criar_banco()

    consulta = """
        SELECT *
        FROM cancelamentos
    """

    parametros: list[Any] = []

    if status:
        consulta += " WHERE status = ?"
        parametros.append(status)

    consulta += """
        ORDER BY criado_em DESC, id DESC
        LIMIT ?
    """

    parametros.append(limite)

    with conectar() as conexao:
        resultados = conexao.execute(
            consulta,
            tuple(parametros),
        ).fetchall()

    return [dict(linha) for linha in resultados]


def atualizar_status_cancelamento(
    cancelamento_id: int,
    status: str,
    resposta_api: str | None = None,
) -> bool:
    """
    Atualiza o estado de um cancelamento.
    """

    status_permitidos = {
        "pendente",
        "simulado",
        "cancelado",
        "liberado",
        "erro",
    }

    if status not in status_permitidos:
        raise ValueError(
            f"Status de cancelamento inválido: {status}"
        )

    with conectar() as conexao:
        cursor = conexao.execute(
            """
            UPDATE cancelamentos
            SET
                status = ?,
                resposta_api = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                resposta_api,
                cancelamento_id,
            ),
        )

        conexao.commit()

    return cursor.rowcount > 0


def obter_cancelamento(
    cancelamento_id: int,
) -> dict[str, Any]:
    """
    Busca um cancelamento pelo ID interno da fila.
    """

    with conectar() as conexao:
        resultado = conexao.execute(
            """
            SELECT *
            FROM cancelamentos
            WHERE id = ?
            LIMIT 1
            """,
            (cancelamento_id,),
        ).fetchone()

    if resultado is None:
        return {}

    return dict(resultado)


def contar_cancelamentos_pendentes() -> int:
    """
    Retorna a quantidade de cancelamentos pendentes.
    """

    criar_banco()

    with conectar() as conexao:
        resultado = conexao.execute(
            """
            SELECT COUNT(*) AS total
            FROM cancelamentos
            WHERE status = 'pendente'
            """
        ).fetchone()

    return int(resultado["total"])

def criar_banco() -> None:
    """
    Cria as tabelas necessárias caso ainda não existam.
    """

    with conectar() as conexao:
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS compras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cpf TEXT NOT NULL,
                produto_id TEXT NOT NULL,
                variante_id TEXT,
                sku TEXT,
                nome_produto TEXT,
                quantidade INTEGER NOT NULL DEFAULT 1,
                pedido_id TEXT NOT NULL,
                numero_pedido TEXT,
                status_pedido TEXT,
                status_pagamento TEXT,
                pedido_criado_em TEXT NOT NULL,
                data_pedido TEXT NOT NULL,
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(pedido_id, produto_id)
            )
            """
        )
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS logs_processamento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id TEXT,
                numero_pedido TEXT,
                cpf TEXT,
                produto_id TEXT,
                variante_id TEXT,
                sku TEXT,
                nome_produto TEXT,
                resultado TEXT NOT NULL,
                motivo TEXT,
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS cancelamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id TEXT NOT NULL,
                numero_pedido TEXT,
                cpf TEXT,
                produto_id TEXT,
                variante_id TEXT,
                sku TEXT,
                nome_produto TEXT,
                motivo TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pendente',
                resposta_api TEXT,
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(pedido_id, produto_id)
            )
            """
        )

        conexao.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cancelamentos_status
            ON cancelamentos(status)
            """
        )

        conexao.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cancelamentos_pedido
            ON cancelamentos(pedido_id)
            """
        )

        conexao.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_logs_pedido_id
            ON logs_processamento(pedido_id)
            """
        )

        conexao.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_logs_resultado
            ON logs_processamento(resultado)
            """
        )


        conexao.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_compras_cpf
            ON compras(cpf)
            """
        )

        conexao.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_compras_produto_id
            ON compras(produto_id)
            """
        )

        conexao.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_compras_pedido_id
            ON compras(pedido_id)
            """
        )

        conexao.commit()


def normalizar_cpf(cpf: str | None) -> str:
    """
    Mantém somente números no CPF.
    """

    if not cpf:
        return ""

    return "".join(caractere for caractere in str(cpf) if caractere.isdigit())

def compra_do_mesmo_pedido_existe(
    pedido_id: int | str,
    produto_id: int | str,
) -> bool:
    """
    Verifica se o produto já foi registrado pelo mesmo pedido.

    Isso evita que o reenvio de um webhook seja tratado
    como uma nova tentativa de compra.
    """

    pedido_id_texto = str(pedido_id)
    produto_id_texto = str(produto_id)

    with conectar() as conexao:
        resultado = conexao.execute(
            """
            SELECT 1
            FROM compras
            WHERE pedido_id = ?
              AND produto_id = ?
            LIMIT 1
            """,
            (
                pedido_id_texto,
                produto_id_texto,
            ),
        ).fetchone()

    return resultado is not None

def compra_ja_existe(
    cpf: str,
    produto_id: int | str,
) -> bool:
    """
    Verifica se o CPF já possui registro para o produto informado.
    """

    cpf_limpo = normalizar_cpf(cpf)
    produto_id_texto = str(produto_id)

    if not cpf_limpo or not produto_id_texto:
        return False

    with conectar() as conexao:
        resultado = conexao.execute(
            """
            SELECT 1
            FROM compras
            WHERE cpf = ?
              AND produto_id = ?
            LIMIT 1
            """,
            (
                cpf_limpo,
                produto_id_texto,
            ),
        ).fetchone()

    return resultado is not None

def buscar_compras_do_dia(
    cpf: str,
    produto_id: int | str,
    data_pedido: str,
    excluir_pedido_id: int | str | None = None,
) -> list[dict[str, Any]]:
    """
    Busca pedidos do mesmo CPF e produto no mesmo dia.

    Pedidos cancelados são ignorados.
    """

    cpf_limpo = normalizar_cpf(cpf)

    consulta = """
        SELECT *
        FROM compras
        WHERE cpf = ?
          AND produto_id = ?
          AND data_pedido = ?
          AND status_pedido != 'cancelled'
    """

    parametros: list[Any] = [
        cpf_limpo,
        str(produto_id),
        data_pedido,
    ]

    if excluir_pedido_id is not None:
        consulta += """
            AND pedido_id != ?
        """

        parametros.append(
            str(excluir_pedido_id)
        )

    consulta += """
        ORDER BY pedido_criado_em ASC, id ASC
    """

    with conectar() as conexao:
        resultados = conexao.execute(
            consulta,
            tuple(parametros),
        ).fetchall()

    return [
        dict(linha)
        for linha in resultados
    ]

def buscar_compra_paga_do_dia(
    cpf: str,
    produto_id: int | str,
    data_pedido: str,
) -> dict[str, Any]:
    """
    Busca uma compra paga do mesmo CPF e produto
    na data informada.

    A comparação do dia utiliza a coluna criado_em.
    Pedidos cancelados são ignorados.
    """

    criar_banco()

    cpf_limpo = normalizar_cpf(cpf)
    produto_id_texto = str(produto_id).strip()
    data_pedido_texto = str(data_pedido).strip()

    if not cpf_limpo:
        return {}

    if not produto_id_texto:
        return {}

    if not data_pedido_texto:
        return {}

    with conectar() as conexao:
        resultado = conexao.execute(
            """
            SELECT *
            FROM compras
            WHERE cpf = ?
              AND CAST(produto_id AS TEXT) = ?
              AND DATE(criado_em) = ?
              AND LOWER(
                    COALESCE(status_pagamento, '')
                  ) = 'paid'
              AND LOWER(
                    COALESCE(status_pedido, '')
                  ) NOT IN (
                    'cancelled',
                    'canceled',
                    'cancelado'
                  )
            ORDER BY criado_em DESC, id DESC
            LIMIT 1
            """,
            (
                cpf_limpo,
                produto_id_texto,
                data_pedido_texto,
            ),
        ).fetchone()

    if resultado is None:
        return {}

    return dict(resultado)


def registrar_compra(
    cpf: str,
    produto_id: int | str,
    pedido_id: int | str,
    pedido_criado_em: str,
    data_pedido: str,
    numero_pedido: int | str | None = None,
    variante_id: int | str | None = None,
    sku: str | None = None,
    nome_produto: str | None = None,
    quantidade: int = 1,
    status_pedido: str | None = None,
    status_pagamento: str | None = None,
) -> bool:
    """
    Registra uma compra.

    Retorna:
        True  -> compra registrada
        False -> CPF já tinha esse produto registrado
    """

    cpf_limpo = normalizar_cpf(cpf)
    produto_id_texto = str(produto_id)
    pedido_id_texto = str(pedido_id)

    if len(cpf_limpo) != 11:
        raise ValueError("CPF inválido ou ausente.")

    if not produto_id_texto:
        raise ValueError("produto_id inválido ou ausente.")

    if not pedido_id_texto:
        raise ValueError("pedido_id inválido ou ausente.")

    try:
        with conectar() as conexao:
            conexao.execute(
                """
                INSERT INTO compras (
                    cpf,
                    produto_id,
                    variante_id,
                    sku,
                    nome_produto,
                    quantidade,
                    pedido_id,
                    numero_pedido,
                    status_pedido,
                    status_pagamento,
                    pedido_criado_em,
                    data_pedido
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cpf_limpo,
                    produto_id_texto,
                    (
                        str(variante_id)
                        if variante_id is not None
                        else None
                    ),
                    sku,
                    nome_produto,
                    int(quantidade),
                    pedido_id_texto,
                    (
                        str(numero_pedido)
                        if numero_pedido is not None
                        else None
                    ),
                    status_pedido,
                    status_pagamento,
                    pedido_criado_em,
                    data_pedido,
                ),
            )

            conexao.commit()

        return True

    except sqlite3.IntegrityError:
        return False


def listar_compras_por_cpf(
    cpf: str,
) -> list[dict[str, Any]]:
    """
    Lista todas as compras registradas para um CPF.
    """

    cpf_limpo = normalizar_cpf(cpf)

    with conectar() as conexao:
        resultados = conexao.execute(
            """
            SELECT *
            FROM compras
            WHERE cpf = ?
            ORDER BY criado_em DESC
            """,
            (cpf_limpo,),
        ).fetchall()

    return [dict(linha) for linha in resultados]


def listar_todas_compras() -> list[dict[str, Any]]:
    """
    Retorna todos os registros da tabela compras.
    """

    with conectar() as conexao:
        resultados = conexao.execute(
            """
            SELECT *
            FROM compras
            ORDER BY criado_em DESC
            """
        ).fetchall()

    return [dict(linha) for linha in resultados]


def remover_compra(
    cpf: str,
    produto_id: int | str,
) -> int:
    """
    Remove um registro pelo CPF e produto.

    Retorna a quantidade de linhas removidas.
    """

    cpf_limpo = normalizar_cpf(cpf)
    produto_id_texto = str(produto_id)

    with conectar() as conexao:
        cursor = conexao.execute(
            """
            DELETE FROM compras
            WHERE cpf = ?
              AND produto_id = ?
            """,
            (
                cpf_limpo,
                produto_id_texto,
            ),
        )

        conexao.commit()

        return cursor.rowcount


def remover_compras_do_pedido(
    pedido_id: int | str,
) -> int:
    """
    Remove todos os produtos relacionados a um pedido.
    """

    with conectar() as conexao:
        cursor = conexao.execute(
            """
            DELETE FROM compras
            WHERE pedido_id = ?
            """,
            (str(pedido_id),),
        )

        conexao.commit()

        return cursor.rowcount


def contar_compras() -> int:
    """
    Retorna a quantidade total de registros no banco.
    """

    with conectar() as conexao:
        resultado = conexao.execute(
            """
            SELECT COUNT(*) AS total
            FROM compras
            """
        ).fetchone()

    return int(resultado["total"])


def teste_banco() -> None:
    """
    Teste temporário para confirmar o funcionamento do banco.
    """

    criar_banco()

    print(f"Banco criado em: {CAMINHO_BANCO}")

    cpf_teste = "123.456.789-00"
    produto_teste = 987654

    existe_antes = compra_ja_existe(
        cpf=cpf_teste,
        produto_id=produto_teste,
    )

    print("Compra existia antes:", existe_antes)

    registrado = registrar_compra(
        cpf=cpf_teste,
        produto_id=produto_teste,
        variante_id=123456,
        sku="SKU-TESTE-40",
        nome_produto="Produto de teste",
        quantidade=1,
        pedido_id=2020473950,
        numero_pedido=614,
        status_pedido="open",
        status_pagamento="paid",
    )

    print("Compra registrada:", registrado)

    existe_depois = compra_ja_existe(
        cpf=cpf_teste,
        produto_id=produto_teste,
    )

    print("Compra existe depois:", existe_depois)

    print("Total de registros:", contar_compras())

    print("\nCompras do CPF:")

    for compra in listar_compras_por_cpf(cpf_teste):
        print(compra)


if __name__ == "__main__":
    teste_banco()