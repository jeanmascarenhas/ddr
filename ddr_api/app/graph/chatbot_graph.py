from typing import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import GOOGLE_API_KEY, GEMINI_MODEL

SYSTEM_PROMPT = """
Você é um assistente corporativo baseado em IA.

Diretrizes:
- Responda em português.
- Seja técnico e objetivo.
- Forneça exemplos quando necessário.
- Não invente informações.
- Quando houver incerteza, informe explicitamente.
"""

class ChatState(TypedDict):
    messages: list[BaseMessage]

llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=GOOGLE_API_KEY,
    temperature=0.4
)

def chatbot_node(state):

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        *state["messages"]
    ]

    response = llm.invoke(messages)

    return {
        "messages": [
            *state["messages"],
            AIMessage(content=response.content)
        ]
    }

builder = StateGraph(ChatState)

builder.add_node(
    "chatbot",
    chatbot_node
)

builder.add_edge(
    START,
    "chatbot"
)

builder.add_edge(
    "chatbot",
    END
)

graph = builder.compile()