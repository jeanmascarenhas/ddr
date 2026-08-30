from fastapi import FastAPI

from app.routers.chat import router as chat_router

app = FastAPI(
    title="Data Fast",
    version="1.0.0",
    description="Chatbot utilizando FastAPI + LangGraph + Gemini"
)

app.include_router(chat_router)


@app.get("/")
def root():

    return {
        "status": "online"
    }