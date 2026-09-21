from functools import lru_cache
from dataclasses import dataclass, field
from sqlalchemy import inspect
from app.db.engine import get_engine
from app.config import DB_SCHEMA


@dataclass
class ColumnNote:
    note: str


@dataclass
class TableMeta:
    description: str                              # resumo de negócio (entra no table_index)
    column_notes: dict[str, str] = field(default_factory=dict)   # coluna -> observação
    extra_notes: list[str] = field(default_factory=list)         # regras gerais da tabela
    skip_columns: list[str] = field(default_factory=list)        # colunas a esconder do DDL
    joins_available: dict[str, str] = field(default_factory=dict)  # fk_column -> "tabela(col) — status"


# ---------------------------------------------------------------------
# Cadastro central de metadados. Uma entrada por tabela do escopo da POC.
# ---------------------------------------------------------------------
TABLE_METADATA: dict[str, TableMeta] = {
    "product_product": TableMeta(
        description="Variantes de produto (Odoo) — SKU, código de barras, preço de custo, peso/volume",
        column_notes={
            "standard_price": (
                "jsonb, campo multi-empresa. Para extrair como número use "
                "(standard_price->>'1')::numeric — '1' é o company_id padrão desta POC."
            ),
            "lot_properties_definition": "jsonb — não usar em filtros/agregações nesta POC.",
            "default_code": "SKU interno (referência interna do produto).",
            "barcode": "Código de barras (EAN).",
            "active": "false = produto arquivado/descontinuado. Por padrão filtre active = true.",
        },
        joins_available={
            "product_tmpl_id": "product_template(id) — indisponível nesta POC, não faça JOIN",
            "create_uid": "res_users(id) — indisponível nesta POC, não faça JOIN",
            "write_uid": "res_users(id) — indisponível nesta POC, não faça JOIN",
        },
        extra_notes=[
            "Esta tabela não tem nome/descrição do produto — apenas product_template teria. "
            "Perguntas por nome de produto não podem ser respondidas só com esta tabela.",
        ],
    ),
    # próxima tabela entra aqui, mesmo padrão:
    # "product_template": TableMeta(...)
}


BUSINESS_GLOSSARY = {k: v.description for k, v in TABLE_METADATA.items()}


def get_meta(table: str) -> TableMeta:
    return TABLE_METADATA.get(table.lower(), TableMeta(description=""))


@lru_cache(maxsize=1)
def table_index() -> str:
    insp = inspect(get_engine())
    linhas = []
    for t in insp.get_table_names(schema=DB_SCHEMA):
        if t.lower() not in TABLE_METADATA:
            continue
        linhas.append(f"- {DB_SCHEMA}.{t}: {BUSINESS_GLOSSARY[t.lower()]}")
    return "\n".join(linhas)


@lru_cache(maxsize=256)
def table_ddl(table: str) -> str:
    insp = inspect(get_engine())
    meta = get_meta(table)

    cols = insp.get_columns(table, schema=DB_SCHEMA)
    pk = insp.get_pk_constraint(table, schema=DB_SCHEMA).get("constrained_columns", [])

    linhas = [f"TABELA {DB_SCHEMA}.{table}"]
    for c in cols:
        nome = c["name"]
        if nome in meta.skip_columns:
            continue
        flag = " [PK]" if nome in pk else ""
        linha = f"  {nome} {c['type']}{flag}"
        if nome in meta.column_notes:
            linha += f"  -- {meta.column_notes[nome]}"
        linhas.append(linha)

    if meta.joins_available:
        linhas.append("  FKs:")
        for col, destino in meta.joins_available.items():
            linhas.append(f"    {col} -> {destino}")

    if meta.extra_notes:
        linhas.append("  Observações:")
        for n in meta.extra_notes:
            linhas.append(f"    - {n}")

    return "\n".join(linhas)


def allowed_tables() -> set[str]:
    return set(TABLE_METADATA.keys())