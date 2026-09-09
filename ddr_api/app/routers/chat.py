from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
import asyncio

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