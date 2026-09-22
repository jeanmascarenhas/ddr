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


# @router.post(
#     "",
#     response_model=ChatResponse
# )
# async def chat(request: ChatRequest):
#     result = graph.invoke(
#         {
#             "messages": [
#                 HumanMessage(content=request.prompt)
#             ]
#         }
#     )

#     try:
#         return ChatResponse(
#             response=result["messages"][-1].content[0]["text"]
#         )
#     except Exception as e:
#             return f"Error {e}"

    
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

    try:
        return ChatResponse(
            response=result["messages"][-1].content[0]["text"]
        )
    except Exception as e:
            return f"Error {e}"


@router.post(
     "/fake",
     response_model=ChatResponse, tags=["Fake"]
)
async def fake_chat(request: ChatRequest):

    full_text =f"""Fake response for prompt: {request.prompt} +\n
                        Sed ut perspiciatis unde omnis iste natus error sit voluptatem
                        accusantium doloremque laudantium, totam rem aperiam, eaque 
                        ipsa quae ab illo inventore veritatis et quasi architecto  
                        beatae vitae dicta sunt explicabo. Nemo enim ipsam 
                        voluptatem quia voluptas sit aspernatur aut odit aut 
                        fugit, sed quia consequuntur magni dolores eos qui 
                        ratione voluptatem sequi nesciunt. Neque porro quisquam est, 
                        qui dolorem ipsum quia dolor sit amet, consectetur, adipisci 
                        velit, sed quia non numquam eius modi tempora incidunt ut 
                        labore et dolore magnam aliquam quaerat voluptatem. Ut enim 
                        ad minima veniam, quis nostrum exercitationem ullam corporis 
                        suscipit laboriosam, nisi ut aliquid ex ea commodi consequatur? 
                        Quis autem vel eum iure reprehenderit qui in ea voluptate velit 
                        esse quam nihil molestiae consequatur, vel illum qui dolorem eum 
                        fugiat quo voluptas nulla pariatur?"""

    async def generate():
         words = full_text.split(" ")
         for word in words:
             yield word + " "
            #  await asyncio.sleep(0.002)

    return StreamingResponse(generate(), media_type="text/plain")
NODE_LABELS = {
    "select_tables": "🔍 Selecionando tabelas relevantes...",
    "generate_sql": "🧠 Gerando consulta SQL...",
    "validate_sql": "✅ Validando SQL...",
    "execute_sql": "⚙️ Executando no banco...",
    "answer": "📝 Montando resposta...",
}


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    def gerar():
        inicio = time.perf_counter()
        try:
            for update in sql_graph.stream(
                {"question": request.prompt}, stream_mode="updates"
            ):
                for node_name, node_output in update.items():
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
            yield sse("error", {"detail": str(e)})

    return StreamingResponse(gerar(), media_type="text/event-stream")
