from typing import Optional

import chainlit as cl


@cl.password_auth_callback
async def auth_callback(
    username: str,
    password: str,
) -> Optional[cl.User]:

    # Futuramente:
    # user = await buscar_usuario_no_banco(username)
    #
    # if not user:
    #     return None
    #
    # if not verificar_senha(password, user.password_hash):
    #     return None

    # Apenas para teste inicial
    if username == "admin" and password == "admin":
        return cl.User(
            identifier=username,
            metadata={
                "role": "admin",
            },
        )

    return None