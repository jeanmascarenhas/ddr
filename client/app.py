import logging

import chainlit as cl
import httpx

BACKEND_URL = "http://localhost:8000"


# @cl.on_message
# async def on_message(message: cl.Message):
#     await cl.Message(content=f"Você disse: {message.content}").send()


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



# ##Fake request to be used in first version
# @cl.on_message
# async def on_message(message: cl.Message):
#     async with httpx.AsyncClient() as client:
#         response = await client.post(
#             f"{BACKEND_URL}/chat/fake",
#             json={"prompt": message.content},
#         )
#         data = response.json()
#         await cl.Message(content=data["response"]).send()

# ##Fake request to be used in second version
# @cl.on_message
# async def on_message(message: cl.Message):
#     msg = cl.Message(content="")
#     await msg.send()

#     async with httpx.AsyncClient() as client:

#         async with client.stream(
#             "POST",
#             f"{BACKEND_URL}/chat/fake",
#             json={"prompt": message.content},
#         ) as response:
#             async for line in response.aiter_lines():
#                 if line:
#                     await msg.stream_token(line)

#     await msg.update()

##Fake request to be used in third version
@cl.on_message
async def on_message(message: cl.Message):
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
