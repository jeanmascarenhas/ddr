# Data Fast

Agente de Inteligência Artificial Generativa integrado a um ERP, capaz de interpretar perguntas em linguagem natural e convertê-las em consultas SQL (**Text-to-SQL**), retornando dados diretamente do banco relacional sem a necessidade de navegação por telas, filtros e relatórios tradicionais.

Este projeto é a implementação prática (prova de conceito) de uma pesquisa acadêmica que investiga se agentes baseados em LLMs conseguem reduzir o tempo de obtenção de informações em sistemas ERP, mantendo níveis adequados de precisão, quando comparados ao uso convencional do sistema.

---

## Contexto da pesquisa

### Pergunta de pesquisa

Como um agente de Inteligência Artificial Generativa integrado a um ERP pode facilitar e agilizar a consulta de dados via linguagem natural, em comparação ao uso tradicional das telas e filtros do sistema?

### Hipótese

**H1:** Um agente de Inteligência Artificial Generativa capaz de converter perguntas em linguagem natural em consultas SQL reduz o tempo de obtenção de informações e a complexidade operacional das consultas em um sistema ERP, mantendo níveis adequados de precisão nos resultados, quando comparado ao uso tradicional de telas, filtros e relatórios do sistema.

**H0 (hipótese nula):** Não há diferença relevante entre a utilização de um agente de IA Generativa e o uso tradicional das funcionalidades do ERP em relação ao tempo de obtenção das informações e à precisão dos resultados retornados.

### Objetivo geral

Analisar como um agente de Inteligência Artificial Generativa integrado a um ERP pode facilitar e agilizar a consulta de dados via linguagem natural, em comparação ao uso tradicional das telas e filtros do sistema.

### Objetivos específicos

- Identificar os principais conceitos e abordagens relacionados à IA Generativa, LLMs, agentes inteligentes e técnicas de Text-to-SQL aplicadas à consulta de dados em sistemas ERP;
- Estruturar um ambiente experimental utilizando o ERP **Odoo Community** e o banco de dados **PostgreSQL**, com dados representativos de processos empresariais;
- Desenvolver um agente de IA Generativa capaz de interpretar consultas em linguagem natural e gerar consultas SQL para obtenção de informações no banco do ERP;
- Definir um conjunto padronizado de cenários de consulta para comparar o agente de IA com o método tradicional do ERP;
- Mensurar tempo de obtenção das informações, precisão dos resultados e complexidade operacional nas duas abordagens;
- Comparar os resultados do agente de IA Generativa com os do método tradicional, identificando ganhos e limitações da abordagem conversacional.

---

## Arquitetura do agente

O projeto é a implementação técnica que dá suporte à pesquisa: um agente construído com **LangGraph**, orquestrando um fluxo de geração, validação e execução de SQL de forma segura e auditável sobre o banco do ERP.

```
START
  ↓
select_tables   → seleciona as tabelas relevantes para a pergunta
  ↓
generate_sql    → o LLM (Gemini) gera um SELECT com base no schema
  ↓
validate_sql    → validação estrutural via AST (sqlglot): só SELECT,
                  só tabelas permitidas, LIMIT forçado
  ↓ (erro → retorna a generate_sql com o motivo, até MAX_SQL_RETRIES)
execute_sql     → execução em conexão read-only, com statement_timeout
  ↓
answer          → o LLM converte o resultado em resposta em português
  ↓
END
```

O ciclo de correção automática realimenta o LLM com o erro do banco ou da validação, permitindo que o agente corrija o próprio SQL antes de responder ao usuário.

### Camadas de segurança

1. Usuário de banco dedicado, somente leitura (`GRANT SELECT` restrito às tabelas do escopo);
2. Validador AST que bloqueia comandos de escrita/DDL e tabelas fora do escopo permitido;
3. Transação `read-only` e `statement_timeout` na conexão;
4. `LIMIT` forçado em toda consulta gerada.

---

## Stack

| Camada | Tecnologia |
|---|---|
| API | FastAPI |
| Orquestração do agente | LangGraph |
| LLM | Google Gemini (`langchain-google-genai`) |
| Banco de dados | PostgreSQL (ambiente experimental: ERP Odoo Community) |
| Validação de SQL | sqlglot |
| Driver de banco | SQLAlchemy + psycopg |

---

## Estrutura do projeto

```
app/
├── config.py                 # variáveis de ambiente (API key, modelo, banco, limites)
├── main.py                   # inicialização do FastAPI
├── db/
│   ├── engine.py              # engine do banco (lazy) e execução read-only
│   ├── catalog.py             # catálogo de tabelas/colunas exposto ao LLM
│   └── guard.py                # validação AST do SQL gerado
├── graph/
│   ├── sql_agent_graph.py     # grafo do agente (LangGraph)
│   └── llm_utils.py            # normalização da resposta do LLM
├── models/
│   └── chat_models.py         # schemas Pydantic (request/response)
└── routers/
    └── chat.py                # endpoints /chat e /chat/stream
```

---

## Como executar o backend

### Pré-requisitos

- Python 3.11+
- PostgreSQL acessível (ambiente experimental com o ERP Odoo Community)
- Chave de API do Google Gemini

### Passo a passo

```powershell
# criar o ambiente virtual
python -m venv venv

# ativar o ambiente virtual (Windows)
.\venv\Scripts\activate

# instalar as dependências
pip install -r .\requirements.txt
```

### Variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
GOOGLE_API_KEY=sua_chave_aqui
GEMINI_MODEL=gemini-2.5-flash

DATABASE_URL=postgresql+psycopg://usuario:senha@localhost:5432/banco
DB_SCHEMA=public

MAX_ROWS=200
STATEMENT_TIMEOUT_MS=15000
MAX_SQL_RETRIES=2
```

> Use um usuário de banco **somente leitura**, restrito às tabelas do escopo do experimento — nunca a credencial administrativa do ERP.

### Subir a API

```powershell
uvicorn app.main:app --reload
```

A API sobe em `http://localhost:8000`. Documentação interativa em `http://localhost:8000/docs`.

---

## Endpoints

### `POST /chat`

Executa o fluxo completo e retorna a resposta final.

```json
{
  "prompt": "quantos produtos ativos existem?"
}
```

Resposta:

```json
{
  "answer": "Existem 42 produtos ativos.",
  "sql": "SELECT COUNT(*) FROM product_product WHERE active = true LIMIT 200",
  "columns": ["count"],
  "rows": [{"count": 42}],
  "row_count": 1,
  "attempts": 1,
  "elapsed_ms": 1830,
  "error": null
}
```

### `POST /chat/stream`

Mesma consulta, mas transmitida em tempo real via SSE, expondo cada etapa do agente (seleção de tabelas, geração de SQL, validação, execução, correção em caso de erro e resposta final) conforme o grafo avança.

---

## Escopo atual da POC

A validação inicial está restrita à tabela `product_product` (Odoo), incluindo tratamento específico para o campo `standard_price` (armazenado como `jsonb`, multi-empresa). O catálogo de tabelas foi desenhado para ser expansível — novas tabelas do ERP podem ser adicionadas ao escopo sem alterar a lógica do agente.

## Avaliação experimental

Para sustentar a análise da hipótese (H1 vs. H0), a avaliação da POC deve comparar, para um conjunto padronizado de perguntas:

- **Tempo de obtenção da informação** via agente de IA vs. via telas/filtros do ERP;
- **Precisão dos resultados** retornados pelo agente, frente a um gabarito validado manualmente;
- **Complexidade operacional**, medida pelo número de etapas necessárias em cada abordagem.
