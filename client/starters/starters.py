import chainlit as cl


@cl.set_starters
async def set_starters(
    user: cl.User | None = None, language: str | None = None
) -> list[cl.Starter]:
    """Return the starter prompts displayed when a chat is opened."""
    del user, language

    return [
        cl.Starter(
            label="Notas mais recentes",
            message="Traga-me as 5 notas fiscais mais recentes",
            command="recent_invoices",
            icon="/public/idea.svg",
        ),
        cl.Starter(
            label="Notas por período",
            message="Traga-me as notas fiscais emitidas entre 01/01/2023 e 31/12/2023",
            command="invoices_by_period",
            icon="/public/calendar.svg",
        ),
    ]

# @cl.set_starters
# async def set_starters():
#     current_user = cl.user_session.get("user")
#     if current_user and current_user.metadata.get("role") == "admin":

#         return [
#             cl.Starter(
#             label="Notas mais recentes",
#             message="Traga-me as 5 notas fiscais mais recentes",
#             command="recent_invoices",
#             icon="/public/idea.svg",
#             ),
#             cl.Starter(
#                 label="Notas por período",
#                 message="Traga-me as notas fiscais emitidas entre 01/01/2023 e 31/12/2023",
#                 command="invoices_by_period",
#                 icon="/public/calendar.svg",
#             ),
#         ]

    
#     return [
#         cl.Starter(
#             label="Notas mais recentes",
#             message="Traga-me as 5 notas fiscais mais recentes",
#             command="recent_invoices",
#             icon="/public/idea.svg",
#         ),
#     ]
