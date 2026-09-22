import logging
import os

import chainlit as cl
import httpx

import starters.starters

from auth.authentication import auth_callback

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://localhost:8000",
)

@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("counter", 0)
    user = cl.user_session.get("user")

    if user:
        logging.info(f"User {user.identifier} has started a chat session.")
    else:
        cl.user_session.set("user", cl.User(identifier="guest", metadata={"role": "guest"}))



##Fake request to be used in third version
@cl.on_message
async def on_message(message: cl.Message):
    # counter = cl.user_session.get("counter")
    # counter = counter + 1 if counter is not None else 1
    # cl.user_session.set("counter", counter)

    user = cl.user_session.get("user")

    if not user:
            await cl.Message(
            content="Usuário não autenticado."
        ).send()
            return

    counter = cl.user_session.get("counter", 0)
    counter = counter + 1 if counter is not None else 1
    cl.user_session.set("counter", counter)

    msg = cl.Message(content="")
    await msg.send()

    try:
        async with httpx.AsyncClient() as client:

            async with client.stream(
                "POST",
                f"{BACKEND_URL}/chat/fake",
                json={"prompt": message.content},
            ) as response:
                async for chunk in response.aiter_bytes():
                    if chunk:
                        await msg.stream_token(chunk.decode("utf-8"))
                                        

        await msg.update()

    except httpx.RequestError as e:
        logging.error(f"Error occurred while making the request: {e}")
        await cl.Message(
            content="Error on communicating with the backend."
        ).send()

    except httpx.HTTPStatusError as e:

        logging.error(
            "Backend returned HTTP error: %s",
            e,
        )

        await cl.Message(
            content="O backend retornou um erro."
        ).send()

@cl.on_chat_end
async def on_chat_end():
    user = cl.user_session.get("user")
    if user:
        logging.info(f"User {user.identifier} has ended the chat session.")
    else:
        logging.info("A guest user has ended the chat session.")

# @cl.set_starters
# async def set_starters(
#     user: cl.User | None = None, language: str | None = None
# ) -> list[cl.Starter]:
#     """Return the starter prompts displayed when a chat is opened."""
#     del user, language

#     return [
#         cl.Starter(
#             label="Notas mais recentes",
#             message="Traga-me as 5 notas fiscais mais recentes",
#             command="recent_invoices",
#             icon="/public/idea.svg",
#         ),
#         cl.Starter(
#             label="Notas por período",
#             message="Traga-me as notas fiscais emitidas entre 01/01/2023 e 31/12/2023",
#             command="invoices_by_period",
#             icon="/public/calendar.svg",
#         ),
#     ]



## Request to be used in final version
# @cl.on_message
# async def on_message(message: cl.Message):

#     async with httpx.AsyncClient() as client:
#         response = await client.post(
#             f"{BACKEND_URL}/chat",
#             json={"message": message.content},
#         )
#         data = response.json()
#         await cl.Message(content=data["response"]).send()