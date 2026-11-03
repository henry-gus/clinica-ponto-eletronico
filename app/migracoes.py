"""Acrescenta colunas novas em bancos que já existem.

O `create_all` cria tabelas que faltam, mas não altera tabelas existentes. Como o projeto
ainda é pequeno, isto cobre a necessidade. Se o esquema continuar mudando com frequência,
o caminho certo é adotar o Alembic.
"""
from sqlalchemy import inspect, text

COLUNAS_NOVAS = {
    "usuarios": {
        "papel": "VARCHAR NOT NULL DEFAULT 'funcionario'",
        "dias_trabalho": "VARCHAR NOT NULL DEFAULT '0,1,2,3,4'",
        "data_inicio": "DATE",
        "saldo_inicial": "FLOAT NOT NULL DEFAULT 0",
    },
    "marcacoes": {
        "manual": "INTEGER NOT NULL DEFAULT 0",
        "registrado_por": "INTEGER REFERENCES usuarios(id)",
    },
}


def migrar_esquema(engine) -> list[str]:
    """Devolve as colunas que foram acrescentadas (lista vazia se o banco já estava em dia)."""
    inspetor = inspect(engine)
    acrescentadas = []
    for tabela, colunas in COLUNAS_NOVAS.items():
        if not inspetor.has_table(tabela):
            continue
        existentes = {coluna["name"] for coluna in inspetor.get_columns(tabela)}
        for nome, definicao in colunas.items():
            if nome not in existentes:
                with engine.begin() as conexao:
                    conexao.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {definicao}"))
                acrescentadas.append(f"{tabela}.{nome}")
    return acrescentadas
