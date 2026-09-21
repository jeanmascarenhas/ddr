import sqlglot
from sqlglot import exp

BLOQUEADOS = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create,
    exp.Alter, exp.TruncateTable, exp.Grant, exp.Commit, exp.Command,
)


class SQLInvalido(Exception):
    pass


def validar_e_normalizar(sql: str, tabelas_ok: set[str], max_rows: int) -> str:
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except Exception as e:
        raise SQLInvalido(f"SQL não parseável: {e}")

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SQLInvalido("Envie exatamente um comando SQL, sem ';' múltiplos.")

    stmt = statements[0]

    if not isinstance(stmt, (exp.Select, exp.Union, exp.Subquery)):
        raise SQLInvalido("Apenas comandos SELECT são permitidos.")

    for node in stmt.walk():
        if isinstance(node, BLOQUEADOS):
            raise SQLInvalido("Comando de escrita/DDL detectado. Apenas leitura é permitida.")

    for tabela in stmt.find_all(exp.Table):
        nome = tabela.name.lower()
        if nome not in tabelas_ok:
            raise SQLInvalido(
                f"Tabela '{nome}' não está no escopo permitido. "
                f"Use apenas as tabelas listadas no catálogo."
            )

    if not stmt.args.get("limit"):
        stmt = stmt.limit(max_rows)

    return stmt.sql(dialect="postgres")