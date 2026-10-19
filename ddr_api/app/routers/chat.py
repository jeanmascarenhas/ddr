from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
import asyncio
import json
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from app.graph.sql_agent_graph import sql_graph

from app.models.chat_models import (
    ChatRequest,
    ChatResponse
)

from app.graph.chatbot_graph import graph

router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)

    
@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    inicio = time.perf_counter()
    try:
        result = await sql_graph.ainvoke({"question": request.prompt})
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Falha no agente: {e}")

    return ChatResponse(
        answer=result.get("answer", ""),
        sql=result.get("sql"),
        columns=result.get("columns", []),
        rows=result.get("rows", []),
        row_count=len(result.get("rows", [])),
        attempts=result.get("attempts", 0),
        elapsed_ms=int((time.perf_counter() - inicio) * 1000),
        error=result.get("error"),
    )

NODE_LABELS = {
    "select_tables": "🔍 Selecionando tabelas relevantes...",
    "generate_sql": "🧠 Gerando consulta SQL...",
    "validate_sql": "✅ Validando SQL...",
    "execute_sql": "⚙️ Executando no banco...",
    "answer": "📝 Montando resposta...",
}


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


FAKE_LOREM = (
    "Sed ut perspiciatis unde omnis iste natus error sit voluptatem "
    "accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo "
    "inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo. "
    "Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, "
    "sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt."
)

FAKE_STEPS = [
    ("select_tables", {"tables": ["clientes", "pedidos"]}),
    ("generate_sql", {"sql": "SELECT c.nome, COUNT(*) AS total\nFROM pedidos p\nJOIN clientes c ON c.id = p.cliente_id\nGROUP BY c.nome;"}),
    ("validate_sql", {"attempts": 1}),
    ("execute_sql", {}),
]


@router.post("/fake", tags=["Fake"])
async def fake_chat(request: ChatRequest):
    async def generate():
        inicio = time.perf_counter()
        try:
            for node_name, detail in FAKE_STEPS:
                yield sse("step", {
                    "node": node_name,
                    "label": NODE_LABELS.get(node_name, node_name),
                    "detail": detail,
                })
                await asyncio.sleep(0.2)  # simula latência; remova se quiser instantâneo

            yield sse("step", {
                "node": "answer",
                "label": NODE_LABELS["answer"],
                "detail": {},
            })
            yield sse("final", {
                "answer": f"Fake response for prompt: {request.prompt}\n\n{FAKE_LOREM}",
                "elapsed_ms": int((time.perf_counter() - inicio) * 1000),
            })
        except Exception as e:
            yield sse("error", {"message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    async def gerar():
        inicio = time.perf_counter()
        try:
            async for update in sql_graph.astream(
                {"question": request.prompt}, stream_mode="updates"
            ):
                for node_name, node_output in update.items():
                    node_output = node_output or {}

                    yield sse("step", {
                        "node": node_name,
                        "label": NODE_LABELS.get(node_name, node_name),
                        "detail": {
                            k: v for k, v in node_output.items()
                            if k in ("tables", "sql", "error", "attempts")
                        },
                    })

                    if node_name == "answer":
                        yield sse("final", {
                            "answer": node_output.get("answer", ""),
                            "elapsed_ms": int((time.perf_counter() - inicio) * 1000),
                        })
        except Exception as e:
            print("Erro no stream")
            yield sse("error", {"message": str(e)})

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
