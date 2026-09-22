# app/graph/llm_utils.py
def extract_text(response) -> str:
    """Normaliza response.content do LangChain, que pode vir como
    str ou como list de blocos, dependendo do modelo/SDK."""
    content = response.content

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        partes = []
        for bloco in content:
            if isinstance(bloco, str):
                partes.append(bloco)
            elif isinstance(bloco, dict) and "text" in bloco:
                partes.append(bloco["text"])
        return "".join(partes).strip()

    return str(content).strip()