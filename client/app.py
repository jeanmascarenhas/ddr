import json
import logging
import os

import chainlit as cl
import httpx

from auth.authentication import auth_callback  # noqa: F401

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

async def iter_sse(response: httpx.Response):
    """Parseia um stream SSE e gera tuplas (event, data_dict)."""
    event = "message"
    data_lines: list[str] = []

    async for line in response.aiter_lines():
        if line == "":
            # linha em branco = fim do evento
            if data_lines:
                raw = "\n".join(data_lines)
                try:
                    yield event, json.loads(raw)
                except json.JSONDecodeError:
                    logging.warning("SSE com JSON inválido: %s", raw)
            event, data_lines = "message", []
        elif line.startswith(":"):
            continue  # comentário / keep-alive
        elif line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].lstrip())

    # fecha evento pendente caso o stream termine sem linha em branco
    if data_lines:
        try:
            yield event, json.loads("\n".join(data_lines))
        except json.JSONDecodeError:
            pass


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("counter", 0)
    user = cl.user_session.get("user")

    if user:
        logging.info(f"User {user.identifier} has started a chat session.")
    else:
        cl.user_session.set(
            "user", cl.User(identifier="guest", metadata={"role": "guest"})
        )


@cl.on_message
async def on_message(message: cl.Message):
    user = cl.user_session.get("user")
    if not user:
        await cl.Message(content="Usuário não autenticado.").send()
        return

    counter = cl.user_session.get("counter", 0) or 0
    cl.user_session.set("counter", counter + 1)

    msg = cl.Message(content="")
    answered = False

    try:
        timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{BACKEND_URL}/chat/stream",
                json={"prompt": message.content},
                headers={"Accept": "text/event-stream"},
            ) as response:
                response.raise_for_status()

                async for event, data in iter_sse(response):
                    if event == "step":
                        await render_step(data)

                    elif event == "final":
                        answered = True
                        await msg.stream_token(data.get("answer", ""))

                    elif event == "error":
                        logging.error("Erro vindo do backend: %s", data)
                        await cl.Message(
                            content=data.get("message", "O backend retornou um erro.")
                        ).send()
                        return

        if answered:
            await msg.send()  # finaliza a mensagem (já com o conteúdo streamado)
        else:
            await cl.Message(content="O backend não retornou uma resposta.").send()

    except httpx.HTTPStatusError as e:
        logging.error("Backend retornou HTTP %s: %s", e.response.status_code, e)
        await cl.Message(content="O backend retornou um erro.").send()

    except httpx.RequestError as e:
        logging.error("Erro ao comunicar com o backend: %s", e)
        await cl.Message(content="Erro ao comunicar com o backend.").send()


async def render_step(data: dict):
    """Cria um cl.Step por etapa do agente, com SQL/detalhes no output."""
    detail = data.get("detail") or {}

    async with cl.Step(name=data.get("label", data.get("node", "step"))) as step:
        step.show_input = False

        sql = detail.get("sql")
        if sql:
            step.language = "sql"
            step.output = sql
        elif detail.get("tables"):
            step.output = "Tabelas: " + ", ".join(detail["tables"])
        elif detail.get("error"):
            step.output = f"Erro: {detail['error']}"


@cl.on_chat_end
async def on_chat_end():
    user = cl.user_session.get("user")
    if user:
        logging.info(f"User {user.identifier} has ended the chat session.")
    else:
        logging.info("A guest user has ended the chat session.")