from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import (
    GOOGLE_API_KEY, GEMINI_MODEL, MAX_ROWS, MAX_SQL_RETRIES,
)
from app.db.catalog import table_index, table_ddl, allowed_tables
from app.db.guard import validar_e_normalizar, SQLInvalido
from app.db.engine import run_select
from app.graph.llm_utils import extract_text


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

def select_tables(state: SQLState) -> SQLState:
    prompt = f"""Catálogo de tabelas disponíveis:
{table_index()}

Pergunta do usuário: {state['question']}

Liste APENAS os nomes das tabelas necessárias para responder,
separados por vírgula, sem schema e sem nenhum outro texto.
Máximo de 5 tabelas."""

    # resp = llm_sql.invoke([HumanMessage(content=prompt)]).content
    # escolhidas = [t.strip().lower() for t in resp.split(",") if t.strip()]
    resp = extract_text(llm_sql.invoke([HumanMessage(content=prompt)]))
    escolhidas = [t.strip().lower() for t in resp.split(",") if t.strip()]
    validas = allowed_tables()
    return {"tables": [t for t in escolhidas if t in validas], "attempts": 0}


SQL_SYSTEM = """Você é um especialista em SQL PostgreSQL para um ERP.

Regras obrigatórias:
- Gere APENAS um comando SELECT. Nunca INSERT, UPDATE, DELETE ou DDL.
- Use somente as tabelas e colunas do schema fornecido. Não invente nomes.
- Sempre qualifique colunas com o alias da tabela.
- Campos texto de ERP costumam ter padding: use TRIM() em comparações.
- Datas costumam ser armazenadas como texto 'YYYYMMDD'; trate conforme o tipo real.
- Responda SOMENTE com o SQL, sem markdown, sem ``` e sem explicações."""


def generate_sql(state: SQLState) -> SQLState:
    schema = "\n\n".join(table_ddl(t) for t in state["tables"]) or "(nenhuma tabela)"

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
    # sql = llm_sql.invoke(
    #     [SystemMessage(content=SQL_SYSTEM), HumanMessage(content="\n".join(partes))]
    # ).content

    # sql = sql.replace("```sql", "").replace("```", "").strip()
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
    Se o resultado estiver vazio, diga isso explicitamente. Não invente números."""

    return {"answer": extract_text(llm_texto.invoke([HumanMessage(content=prompt)]))}

# ------------------------------------------------------------ roteamento

def rota_pos_execucao(state: SQLState) -> str:
    if state.get("error") and state.get("attempts", 0) < MAX_SQL_RETRIES + 1:
        return "generate_sql"
    return "answer"


builder = StateGraph(SQLState)
builder.add_node("select_tables", select_tables)
builder.add_node("generate_sql", generate_sql)
builder.add_node("validate_sql", validate_sql)
builder.add_node("execute_sql", execute_sql)
builder.add_node("answer", answer)

builder.add_edge(START, "select_tables")
builder.add_edge("select_tables", "generate_sql")
builder.add_edge("generate_sql", "validate_sql")
builder.add_edge("validate_sql", "execute_sql")
builder.add_conditional_edges(
    "execute_sql", rota_pos_execucao,
    {"generate_sql": "generate_sql", "answer": "answer"},
)
builder.add_edge("answer", END)

sql_graph = builder.compile()