from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import (
    GOOGLE_API_KEY, GEMINI_MODEL, MAX_ROWS, MAX_SQL_RETRIES,
)
from app.db.catalog import table_index, allowed_tables
from app.db.guard import validar_e_normalizar, SQLInvalido
from app.db.engine import run_select
from app.graph.llm_utils import extract_text

from app.db.catalog import (
    table_index, allowed_tables, expand_related, schema_context, capabilities_text, glossary_text
)

class SQLState(TypedDict, total=False):
    question: str
    tables: list[str]
    sql: str
    error: str | None
    attempts: int
    columns: list[str]
    rows: list[dict[str, Any]]
    answer: str


llm_sql = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL, google_api_key=GOOGLE_API_KEY, temperature=0
)
llm_texto = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL, google_api_key=GOOGLE_API_KEY, temperature=0.3
)

# ---------------------------------------------------------------- nós

SQL_SYSTEM = """Você é um especialista em SQL PostgreSQL para o banco do Odoo (ERP).

Regras obrigatórias:
- Gere APENAS um comando SELECT (CTEs com WITH são permitidos). Nunca INSERT, UPDATE, DELETE ou DDL.
- Use somente as tabelas e colunas do schema fornecido. Não invente nomes.
- Sempre qualifique colunas com o alias da tabela e use JOINs explícitos conforme os "JOINS conhecidos".
- Datas são timestamp/date reais (não texto). Use now(), CURRENT_DATE e INTERVAL, respeitando o fuso das regras.
- Campos jsonb (nome de produto, standard_price) exigem ->> para extrair texto.
- Siga as "Regras de negócio" fornecidas: elas definem 'pendente', 'atrasado', 'divergência', 'material crítico'.
- Retorne colunas legíveis (número do documento, fornecedor, produto, status, datas) com aliases em português sem acentos, e ordene de forma útil.
- Responda SOMENTE com o SQL, sem markdown, sem ``` e sem explicações."""

def select_tables(state: SQLState) -> SQLState:
    prompt = f"""Catálogo de tabelas disponíveis:
    {table_index()}

    Glossário de termos do negócio:
    {glossary_text()}

Mensagem do usuário: {state['question']}

Liste APENAS os nomes das tabelas necessárias para responder,
separados por vírgula, sem schema e sem nenhum outro texto.
- Inclua as tabelas de ligação (ex.: nome do fornecedor exige res_partner;
  nome do produto exige product_product e product_template).
- Máximo de 8 tabelas.
- Se a mensagem NÃO for uma pergunta sobre dados do ERP (saudação, "o que você faz?",
  agradecimento, assunto geral ou algo que as tabelas acima não cobrem),
  responda exatamente: NENHUMA"""

    resp = extract_text(llm_sql.invoke([HumanMessage(content=prompt)]))
    escolhidas = [t.strip().lower() for t in resp.split(",") if t.strip()]
    validas = allowed_tables()
    tabelas = expand_related([t for t in escolhidas if t in validas])
    return {"tables": tabelas, "attempts": 0}

def generate_sql(state: SQLState) -> SQLState:
    # schema = "\n\n".join(table_ddl(t) for t in state["tables"]) or "(nenhuma tabela)"
    schema = schema_context(state["tables"]) or "(nenhuma tabela)"

    partes = [
        f"Schema disponível:\n{schema}",
        f"\nPergunta: {state['question']}",
    ]
    if state.get("error"):
        partes.append(
            f"\nA tentativa anterior falhou.\nSQL gerado:\n{state.get('sql')}"
            f"\nErro:\n{state['error']}\nCorrija o SQL."
        )

    sql = extract_text(llm_sql.invoke(
        [SystemMessage(content=SQL_SYSTEM), HumanMessage(content="\n".join(partes))]
    ))
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return {"sql": sql, "attempts": state.get("attempts", 0) + 1, "error": None}


def validate_sql(state: SQLState) -> SQLState:
    try:
        return {"sql": validar_e_normalizar(state["sql"], allowed_tables(), MAX_ROWS),
                "error": None}
    except SQLInvalido as e:
        return {"error": str(e)}


def execute_sql(state: SQLState) -> SQLState:
    if state.get("error"):
        return {}
    try:
        columns, rows = run_select(state["sql"], MAX_ROWS)
        return {"columns": columns, "rows": rows, "error": None}
    except Exception as e:
        return {"error": str(e).splitlines()[0][:500]}


def answer(state: SQLState) -> SQLState:
    if state.get("error"):
        return {
            "answer": (
                "Não consegui montar uma consulta válida para essa pergunta. "
                f"Último problema: {state['error']}"
            )
        }

    prompt = f"""Pergunta: {state['question']}
    SQL executado:
    {state['sql']}
    Resultado (até {MAX_ROWS} linhas):
    {state['rows']}

    Responda em português, de forma objetiva, apenas com base nesses dados.
    Traduza status técnicos do Odoo (draft=rascunho, purchase=confirmado, assigned=pronto para receber,
    done=concluído, cancel=cancelado, posted=lançada).
    Se o resultado estiver vazio, diga isso explicitamente e resuma em uma frase o critério buscado
    (ex.: "nenhum pedido com saldo a receber"), sem afirmar que o documento não existe se a busca foi por outro tipo de documento."""

    return {"answer": extract_text(llm_texto.invoke([HumanMessage(content=prompt)]))}


CAPABILITIES_SYSTEM = """Você é o Data Fast, um assistente que consulta o ERP Odoo da empresa
usando linguagem natural. Você é somente leitura: não cria, altera nem exclui nada.

{capabilities}

Como responder:
- Português, tom curto e amigável.
- Se for saudação ou pergunta sobre o que você faz, apresente-se e mostre 3 a 5 exemplos de perguntas.
- Se pediu algo fora do escopo (outro assunto ou dados que você não acessa), diga com clareza que
  não consegue responder isso e sugira o que você pode fazer.
- Nunca invente dados do sistema (números de pedido, fornecedores, quantidades)."""


def capabilities(state: SQLState) -> SQLState:
    system = CAPABILITIES_SYSTEM.format(capabilities=capabilities_text())
    resp = llm_texto.invoke(
        [SystemMessage(content=system), HumanMessage(content=state["question"])]
    )
    return {"answer": extract_text(resp)}


# ------------------------------------------------------------ roteamento

def rota_pos_execucao(state: SQLState) -> str:
    if state.get("error") and state.get("attempts", 0) < MAX_SQL_RETRIES + 1:
        return "generate_sql"
    return "answer"

def rota_pos_selecao(state: SQLState) -> str:
    return "generate_sql" if state.get("tables") else "capabilities"


builder = StateGraph(SQLState)
builder.add_node("select_tables", select_tables)
builder.add_node("generate_sql", generate_sql)
builder.add_node("validate_sql", validate_sql)
builder.add_node("execute_sql", execute_sql)
builder.add_node("answer", answer)
builder.add_node("capabilities", capabilities)  

builder.add_edge(START, "select_tables")
# builder.add_edge("select_tables", "generate_sql")
builder.add_conditional_edges(
    "select_tables", rota_pos_selecao,
    {"generate_sql": "generate_sql", "capabilities": "capabilities"},
)
builder.add_edge("generate_sql", "validate_sql")
builder.add_edge("validate_sql", "execute_sql")
builder.add_conditional_edges(
    "execute_sql", rota_pos_execucao,
    {"generate_sql": "generate_sql", "answer": "answer"},
)
builder.add_edge("answer", END)
builder.add_edge("capabilities", END)  

sql_graph = builder.compile()