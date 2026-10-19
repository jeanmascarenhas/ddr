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
    keep_columns: list[str] = field(default_factory=list)       # whitelist (vazio = todas)
    related_tables: list[str] = field(default_factory=list)      # tabelas que costumam vir juntas 
    internal: bool = False   # NOVO: tabela de ligação, não aparece no table_index
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
        keep_columns=["id", "product_tmpl_id", "default_code", "barcode", "active", "standard_price"],
        related_tables=["product_template"],
        extra_notes=[
            "Esta tabela não tem nome/descrição do produto — apenas product_template teria. "
            "Perguntas por nome de produto não podem ser respondidas só com esta tabela.",
        ],
    ),
}

TABLE_METADATA.update({
    "purchase_order": TableMeta(
        description="Pedidos de compra — fornecedor, status, datas, valor e situação de recebimento/faturamento",
        keep_columns=["id", "name", "partner_id", "partner_ref", "state", "locked", "date_order",
                      "date_approve", "date_planned", "effective_date", "receipt_status",
                      "invoice_status", "amount_total", "origin", "company_id","invoice_count"],
        column_notes={
            "name": "Número do pedido (ex.: P00012). Use para localizar 'o pedido X'.",
            "partner_id": "Fornecedor -> res_partner.id",
            "state": "draft=rascunho, sent=cotação enviada, to approve=aguardando aprovação, "
                     "purchase=pedido confirmado, cancel=cancelado (done=bloqueado, em versões que ainda o usam). "
                     "locked=true só indica pedido bloqueado para edição; continua sendo pedido confirmado.",
            "date_planned": "Data prevista de recebimento (prazo do fornecedor).",
            "effective_date": "Data do primeiro recebimento concluído.",
            "receipt_status": "pending=nada recebido, partial=parcial, full=totalmente recebido.",
            "invoice_status": "no=nada a faturar, to invoice=aguardando faturar, invoiced=faturado.",
            "invoice_count": "Quantidade de NFs/faturas ligadas ao pedido. 0 = nenhuma NF lançada ainda.",
        },
        related_tables=["res_partner", "purchase_order_line",
                        "purchase_order_stock_picking_rel", "account_move_purchase_order_rel"],
    ),
    "purchase_order_line": TableMeta(
        description="Itens dos pedidos de compra — produto, quantidade pedida/recebida/faturada e prazo",
        keep_columns=["id", "order_id", "product_id", "name", "product_qty", "qty_received",
                      "qty_invoiced", "qty_to_invoice", "price_unit", "price_subtotal",
                      "date_planned", "state", "partner_id", "display_type","product_uom_id"],
        column_notes={
            "product_qty": "Quantidade pedida.",
            "qty_received": "Quantidade já recebida. Pendente = product_qty - qty_received.",
            "date_planned": "Data prevista de entrega do item.",
            "display_type": "Filtre display_type IS NULL (ignora linhas de seção/nota).",
        },
        related_tables=["purchase_order", "product_product", "product_template","uom_uom"],
    ),
    "stock_picking": TableMeta(
        description="Recebimentos e demais movimentações (pickings) — status, datas previstas e de conclusão",
        keep_columns=["id", "name", "origin", "partner_id", "picking_type_id", "state",
                      "scheduled_date", "date_deadline", "date_done", "backorder_id",
                      "priority", "create_date"],
        column_notes={
            "name": "Número do recebimento (ex.: WH/IN/00005).",
            "origin": "Documento de origem; em recebimento de compra é o purchase_order.name.",
            "state": "draft=rascunho, waiting=aguardando outra operação, confirmed=aguardando disponibilidade, "
                     "assigned=pronto (aguardando conferência/recebimento), done=recebido, cancel=cancelado.",
            "scheduled_date": "Data prevista (UTC).",
            "date_done": "Data de conclusão (UTC).",
            "backorder_id": "Preenchido em recebimento parcial remanescente (indício de divergência).",
        },
        extra_notes=["Não há coluna purchase_id: ligue ao pedido por stock_move.purchase_line_id ou por origin."],
        related_tables=["stock_picking_type", "stock_move", "res_partner"],
    ),
    "stock_move": TableMeta(
        description="Movimentos de estoque (linhas de picking) — produto, quantidade demandada vs. realizada, "
                    "vínculo com pedido de compra e com ordem de produção",
        keep_columns=["id", "picking_id", "product_id", "product_uom_qty", "quantity",
                      "state", "purchase_line_id", "raw_material_production_id", "production_id",
                      "date", "date_deadline", "origin"],
        column_notes={
            "product_uom_qty": "Quantidade demandada/planejada.",
            "quantity": "Quantidade realizada quando state='done' (Odoo 17+).",
            "state": "draft, waiting, confirmed=aguardando disponibilidade, partially_available, "
                     "assigned=reservado, done, cancel.",
            "purchase_line_id": "-> purchase_order_line.id (movimentos de recebimento de compra).",
            "raw_material_production_id": "Preenchido quando o movimento é COMPONENTE de uma OP -> mrp_production.id.",
            "production_id": "Preenchido quando o movimento é o PRODUTO ACABADO de uma OP.",
            "quantity": "Quantidade realizada quando state='done'."
        },
        related_tables=["stock_picking", "product_product", "product_template","purchase_order_line"],
    ),
    "stock_picking_type": TableMeta(
        description="Tipos de operação do estoque (recebimento, expedição, interna, produção)",
        keep_columns=["id", "name", "code", "warehouse_id", "active"],
        column_notes={
            "code": "incoming=recebimento, outgoing=expedição, internal=transferência interna, mrp_operation=produção.",
            "name": "jsonb traduzido: COALESCE(name->>'pt_BR', name->>'en_US').",
        },
    ),
    "account_move": TableMeta(
        description="Faturas/NFs — NF de fornecedor é move_type 'in_invoice'; número, fornecedor, status, datas e valores",
        keep_columns=["id", "name", "ref", "move_type", "state", "partner_id", "invoice_date",
                      "invoice_date_due", "invoice_origin", "amount_total", "amount_residual",
                      "payment_state", "create_date"],
        column_notes={
            "move_type": "in_invoice=NF/fatura de fornecedor, in_refund=devolução. Para NF de compra use 'in_invoice'.",
            "ref": "Referência do fornecedor, normalmente o número da NF.",
            "name": "Número interno do lançamento (ex.: BILL/2026/00001).",
            "state": "draft=rascunho, posted=lançada, cancel=cancelada.",
            "payment_state": "not_paid, in_payment, paid, partial, reversed.",
            "invoice_origin": "Pedido(s) de compra de origem (texto, pode conter vários).",
        },
        extra_notes=["O número da NF pode estar em 'ref' ou em 'name': busque nos dois."],
        related_tables=["res_partner"],
    ),
    "mrp_production": TableMeta(
        description="Ordens de produção — produto, quantidade, status, datas e disponibilidade de componentes",
        keep_columns=["id", "name", "product_id", "product_qty", "state", "date_start",
                      "date_planned_start", "date_finished", "origin", "priority",
                      "reservation_state", "components_availability_state"],
        column_notes={
            "state": "draft, confirmed, progress=em produção, to_close=a encerrar, done, cancel. "
                     "OPs abertas = confirmed, progress ou to_close.",
            "date_start": "Início planejado/real da OP.",
        },
        related_tables=["product_product", "product_template", "stock_move"],
    ),
    "res_partner": TableMeta(
        description="Parceiros — fornecedores e clientes (nome, referência, CNPJ/CPF)",
        keep_columns=["id", "name", "ref", "vat", "active", "supplier_rank", "is_company", "parent_id"],
        column_notes={"vat": "CNPJ/CPF.", "name": "Nome/razão social do fornecedor."},
    ),
    "product_template": TableMeta(
        description="Cadastro de produtos/materiais — nome, código, categoria",
        keep_columns=["id", "name", "default_code", "active", "categ_id", "uom_id", "purchase_ok"],
        column_notes={"name": "jsonb traduzido: COALESCE(name->>'pt_BR', name->>'en_US')."},
    ),
        "purchase_order_stock_picking_rel": TableMeta(
        description="Ligação pedido de compra <-> recebimento",
        keep_columns=["purchase_order_id", "stock_picking_id"],
        internal=True,
    ),
    "account_move_purchase_order_rel": TableMeta(
        description="Ligação NF/fatura <-> pedido de compra",
        keep_columns=["account_move_id", "purchase_order_id"],
        internal=True,
    ),
    "uom_uom": TableMeta(
        description="Unidades de medida (kg, un, m...)",
        keep_columns=["id", "name"],
        column_notes={"name": "jsonb traduzido: COALESCE(name->>'pt_BR', name->>'en_US')."},
    ),
})

BUSINESS_GLOSSARY = {k: v.description for k, v in TABLE_METADATA.items()}  # recalcula após o update

# (tabela_a, tabela_b, como ligar) — só entra no prompt se as duas tabelas foram selecionadas
JOIN_PATHS: list[tuple[str, str, str]] = [
    ("purchase_order", "res_partner", "purchase_order.partner_id = res_partner.id (fornecedor)"),
    ("purchase_order_line", "purchase_order", "purchase_order_line.order_id = purchase_order.id"),
    ("purchase_order_line", "product_product", "purchase_order_line.product_id = product_product.id"),
    ("product_product", "product_template", "product_product.product_tmpl_id = product_template.id (nome do produto)"),
    ("stock_move", "purchase_order_line", "stock_move.purchase_line_id = purchase_order_line.id (liga recebimento ao pedido)"),
    ("stock_move", "stock_picking", "stock_move.picking_id = stock_picking.id"),
    ("stock_move", "product_product", "stock_move.product_id = product_product.id"),
    ("stock_move", "mrp_production", "stock_move.raw_material_production_id = mrp_production.id (componentes da OP)"),
    ("stock_picking", "stock_picking_type", "stock_picking.picking_type_id = stock_picking_type.id"),
    ("stock_picking", "res_partner", "stock_picking.partner_id = res_partner.id"),

    ("mrp_production", "product_product", "mrp_production.product_id = product_product.id"),
    ("account_move", "res_partner", "account_move.partner_id = res_partner.id"),
    ("purchase_order", "purchase_order_stock_picking_rel", "purchase_order_stock_picking_rel.purchase_order_id = purchase_order.id"),
    ("purchase_order_stock_picking_rel", "stock_picking", "purchase_order_stock_picking_rel.stock_picking_id = stock_picking.id (recebimentos do pedido)"),
    ("account_move_purchase_order_rel", "account_move", "account_move_purchase_order_rel.account_move_id = account_move.id"),
    ("account_move_purchase_order_rel", "purchase_order", "account_move_purchase_order_rel.purchase_order_id = purchase_order.id (pedido da NF)"),
    ("purchase_order_line", "uom_uom", "purchase_order_line.product_uom_id = uom_uom.id (unidade)"),
]

# (tabelas que ativam a regra, texto) — conjunto vazio = regra sempre ativa
BUSINESS_RULES: list[tuple[set[str], str]] = [
    (set(), "Busca por número de documento: compare exato ignorando maiúsculas (UPPER(campo) = UPPER('valor')). "
            "Pnnnnn -> purchase_order.name; WH/IN/nnnnn -> stock_picking.name; outros números de NF -> "
            "account_move.ref ou account_move.name. Se a pergunta não informa o número, não invente um."),
    ({"product_template"},
     "Nome do produto: COALESCE(product_template.name->>'pt_BR', product_template.name->>'en_US'). "
     "Para localizar material por nome ou código use ILIKE '%texto%' no nome ou em default_code."),
    ({"stock_picking", "purchase_order", "purchase_order_line", "stock_move", "mrp_production"},
     "Timestamps estão em UTC. 'Hoje' = (campo AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo')::date "
     "= (now() AT TIME ZONE 'America/Sao_Paulo')::date."),
    ({"purchase_order", "purchase_order_line"},
     "Pedido ativo = state IN ('purchase','done'). Ignore linhas com display_type não nulo. "
     "Pedido recebido = receipt_status = 'full' (ou nenhuma linha com qty_received < product_qty). "
     "Recebimento pendente = receipt_status IN ('pending','partial') ou linha com qty_received < product_qty. "
     "Quantidade pendente = product_qty - qty_received. "
     "Quantidade recebida de um material = SUM(purchase_order_line.qty_received) por produto (e unidade), "
     "filtrando pelo pedido quando a pergunta citar um."),
    ({"purchase_order", "account_move"},
     "Status de NF/pedido: retorne purchase_order.name, fornecedor, state, receipt_status, invoice_status, invoice_count e, "
     "via LEFT JOIN em account_move_purchase_order_rel e account_move, o número (ref/name), state e payment_state da fatura, "
     "se existir. Use LEFT JOIN para o pedido aparecer mesmo sem fatura."),
    ({"account_move"},
     "NF de fornecedor: move_type = 'in_invoice' e state <> 'cancel'. O número da NF está em ref (e/ou name). "
     "Para ligar a NF ao pedido use account_move_purchase_order_rel."),
    ({"stock_picking"},
     "Recebimento de compra = stock_picking com stock_picking_type.code = 'incoming'. "
     "'Entregas programadas para hoje' = recebimentos incoming com scheduled_date hoje e state <> 'cancel'; "
     "mostre o status de cada um (pendente ou concluído)."),
    ({"stock_move", "stock_picking", "purchase_order_line"},
     "Divergência de recebimento = (a) picking incoming com backorder_id não nulo (recebimento parcial); "
     "(b) linha de pedido com recebimento concluído e qty_received <> product_qty; "
     "(c) movimento state='done' de picking incoming com quantity <> product_uom_qty. "
     "Na confirmação parcial o Odoo costuma reduzir a demanda do movimento original, então (c) sozinho não detecta falta: "
     "use também (a) e (b). Informe o tipo de divergência."),
    ({"purchase_order", "purchase_order_line"},
     "Atraso por pedido = effective_date > date_planned (recebido com atraso) OU (effective_date IS NULL e "
     "date_planned < now() e pedido não totalmente recebido). Índice de atraso do fornecedor = pedidos atrasados / "
     "pedidos ativos, agrupado por res_partner. Para atraso por item compare stock_picking.date_done com "
     "purchase_order_line.date_planned."),
    ({"stock_picking"},
     "Lead time de recebimento = stock_picking.date_done - stock_picking.create_date, apenas pickings 'incoming' "
     "com state='done'. Apresente média em horas ou dias. "
     "Lead time de compra do fornecedor = purchase_order.effective_date - purchase_order.date_approve."),
    ({"stock_move", "mrp_production"},
     "Material crítico/em falta para produção = stock_move com raw_material_production_id não nulo e "
     "state NOT IN ('assigned','done','cancel'), de OPs com state IN ('confirmed','progress','to_close'). "
     "Cruze com linhas de compra pendentes do mesmo product_id para achar o pedido que cobre a falta. "
     "OP em risco = OP com algum componente nessa condição."),
]

CAPABILITY_EXAMPLES: dict[str, list[str]] = {
    "Consultas operacionais": [
        "O pedido de compra P00012 já foi recebido?",
        "Qual o status da NF 12345 e qual fornecedor enviou?",
        "Qual a quantidade recebida do material X?",
    ],
    "Acompanhamento": [
        "Quais NFs estão aguardando conferência?",
        "Quais pedidos de compra têm recebimento pendente?",
        "Quais entregas estão programadas para hoje?",
        "Quais materiais tiveram divergência no recebimento?",
    ],
    "Análises": [
        "Quais materiais críticos pendentes podem impactar a produção?",
        "Quais fornecedores têm maior índice de atraso?",
        "Qual o lead time médio de recebimento?",
        "Quais pedidos podem impactar ordens de produção por falta de material?",
    ],
}


def expand_related(tables: list[str], limit: int = 12) -> list[str]:
    result = list(dict.fromkeys(tables))
    for t in list(result):
        for r in get_meta(t).related_tables:
            if r in TABLE_METADATA and r not in result:
                result.append(r)
    return result[:limit]


def schema_context(tables: list[str]) -> str:
    sel = {t.lower() for t in tables}
    partes = ["\n\n".join(table_ddl(t) for t in tables)]
    joins = [f"- {txt}" for a, b, txt in JOIN_PATHS if a in sel and b in sel]
    regras = [f"- {txt}" for escopo, txt in BUSINESS_RULES if not escopo or escopo & sel]
    if joins:
        partes.append("JOINS conhecidos:\n" + "\n".join(joins))
    partes.append("Glossário de termos:\n" + glossary_text())
    if regras:
        partes.append("Regras de negócio:\n" + "\n".join(regras))
    return "\n\n".join(partes)


def capabilities_text() -> str:
    areas = "\n".join(f"- {m.description.split(' — ')[0]}" for m in TABLE_METADATA.values())
    exemplos = "\n".join(
        f"{grupo}:\n" + "\n".join(f"  • {q}" for q in qs)
        for grupo, qs in CAPABILITY_EXAMPLES.items()
    )
    return f"Áreas que você consulta:\n{areas}\n\nExemplos de perguntas:\n{exemplos}"

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
        if meta.keep_columns and nome not in meta.keep_columns and nome not in pk:
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

def validar_catalogo() -> None:
    insp = inspect(get_engine())
    existentes = set(insp.get_table_names(schema=DB_SCHEMA))
    for t, meta in TABLE_METADATA.items():
        if t not in existentes:
            print(f"[AUSENTE] tabela {t} (módulo não instalado?)")
            continue
        cols = {c["name"] for c in insp.get_columns(t, schema=DB_SCHEMA)}
        faltando = [c for c in meta.keep_columns if c not in cols]
        if faltando:
            print(f"[{t}] colunas que não existem: {faltando}")

TERM_GLOSSARY: list[str] = [
    "Números no formato P00001, P00002... são PEDIDOS DE COMPRA (purchase_order.name). Quando o usuário citar "
    "'NF', 'nota', 'documento' ou 'material' seguido de um número assim, trate-o como o pedido de compra.",
    "NF/nota de uma compra: a fatura do fornecedor (account_move, move_type='in_invoice') pode ainda não existir. "
    "Consulte purchase_order e account_move; purchase_order.invoice_count = 0 significa que nenhuma NF foi lançada e "
    "invoice_status = 'to invoice' significa recebido e aguardando NF.",
    "'NF aguardando conferência' = (a) faturas de fornecedor em rascunho (account_move.state='draft') OU "
    "(b) pedidos ativos recebidos com invoice_status='to invoice' (NF ainda não lançada). Consulte account_move e purchase_order.",
    "'Material' = produto (product_product/product_template). 'Material do pedido P00001' = produtos das linhas desse pedido "
    "(purchase_order_line).",
]


def glossary_text() -> str:
    return "\n".join(f"- {t}" for t in TERM_GLOSSARY)   