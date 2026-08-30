from fastapi import APIRouter
from langchain_core.messages import HumanMessage

from app.models.chat_models import (
    ChatRequest,
    ChatResponse
)

from app.graph.chatbot_graph import graph

router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)


@router.post(
    "",
    response_model=ChatResponse
)
async def chat(request: ChatRequest):
    result = graph.invoke(
        {
            "messages": [
                HumanMessage(content=request.prompt)
            ]
        }
    )

    try:
        return ChatResponse(
            response=result["messages"][-1].content[0]["text"]
        )
    except Exception as e:
            return f"Error {e}"