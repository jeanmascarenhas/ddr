import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Query

from app.graph.sql_agent_graph import sql_graph
import random
import re

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.db.catalog import schema_context
from app.graph.judge import validar_execucao
from app.reports.batch_report import gerar_html

router = APIRouter(prefix="/batch", tags=["Batch"])

# ddr_api/outputs  (app/routers/batch.py -> parents[2] = ddr_api)
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "outputs"

NUM_MIN, NUM_MAX = 1, 7                       # P00001 até P00007
PADRAO_NUMERO = re.compile(r"\bP\d{5}\b")

PERGUNTAS: list[tuple[str, str]] = [
    ("operacional", "O pedido de compra P00002 já foi recebido?"),
    ("operacional", "Vocês já deram entrada no pedido P00001?"),
    ("operacional", "A mercadoria referente ao pedido de compra P00001 já chegou?"),
    ("operacional", "Gostaria de saber se o recebimento do pedido P00001 já foi concluído no sistema."),
    ("operacional", "O material do pedido P00001 já consta como entregue para nós?"),

    ("operacional", "Qual o status da NF P00002?"),
    ("operacional", "Como está a situação atual da nota fiscal P00002?"),
    ("operacional", "Podem me atualizar sobre o andamento da NF P00002?"),
    ("operacional", "Em que fase de processamento ou pagamento se encontra a nota P00002?"),
    ("operacional", "A NF P00002 já foi liberada ou ainda está pendente?"),

    ("operacional", "Qual fornecedor enviou a NF P00002?"),
    ("operacional", "De qual empresa é essa nota fiscal P00003?"),
    ("operacional", "Quem consta como o emissor da NF P00003?"),
    ("operacional", "Essa nota P00003 está vinculada a qual parceiro de negócio no sistema?"),
    ("operacional", "Vocês sabem me dizer o nome do fornecedor atrelado à NF P00003?"),

    ("operacional", "Qual a quantidade recebida da ordem P00002?"),
    ("operacional", "Quantas unidades da ordem de compra P00001 chegaram na entrega?"),
    ("operacional", "Qual foi o volume total que deu entrada no estoque para a ordem de compra P00001?"),
    ("operacional", "Pode me confirmar o saldo de peças recebidas para o código P00001?"),
    ("operacional", "Quanto do material P00001 nós efetivamente recebemos até o momento?"),

    ("acompanhamento", "Quais NFs estão aguardando conferência?"),
    ("acompanhamento", "Quais pedidos de compra possuem recebimento pendente?"),
    ("acompanhamento", "Quais entregas estão programadas para hoje?"),
    ("acompanhamento", "Quais materiais tiveram divergência durante o recebimento?"),
        
    ("acompanhamento", "Tem alguma nota fiscal na fila para ser conferida?"),
    ("acompanhamento", "Quais são as notas que ainda precisam passar por conferência?"),
    ("acompanhamento", "Pode me listar as NFs que estão pendentes de validação?"),
    ("acompanhamento", "Quais notas fiscais estão paradas esperando a conferência?"),

    ("acompanhamento", "Quais são os pedidos de compra que ainda não deram entrada?"),
    ("acompanhamento", "Tem algum pedido de compra com o recebimento em aberto?"),
    ("acompanhamento", "Lista pra mim os pedidos que estão aguardando a chegada da mercadoria."),
    ("acompanhamento", "Quais ordens de compra ainda estão com status pendente de recebimento?"),

    ("acompanhamento", "O que temos agendado para receber no dia de hoje?"),
    ("acompanhamento", "Quais são as previsões de entrega para a data de hoje?"),
    ("acompanhamento", "Tem alguma mercadoria programada para chegar hoje?"),
    ("acompanhamento", "Pode me passar a lista de entregas previstas para hoje?"),

    ("acompanhamento", "Quais itens apresentaram problemas na hora de dar entrada?"),
    ("acompanhamento", "Houve alguma divergência de material registrada no recebimento?"),
    ("acompanhamento", "Pode me listar quais produtos vieram com diferença no momento da conferência?"),
    ("acompanhamento", "Quais foram os materiais que deram divergência ao serem recebidos?"),

    ("analitica", "Quais materiais críticos estão pendentes de recebimento e podem impactar a produção?"),
    ("analitica", "Quais fornecedores apresentam maior índice de atraso nas entregas?"),
    ("analitica", "Qual o lead time médio entre a chegada do material e a conclusão do recebimento?"),
    ("analitica", "Quais pedidos possuem risco de impactar ordens de produção devido à falta de material?"),

    ("analitica", "Tem algum item crítico atrasado que possa parar a linha de produção?"),
    ("analitica", "Quais insumos essenciais não chegaram ainda e trazem risco de impacto produtivo?"),
    ("analitica", "Quais materiais importantes faltam dar entrada e ameaçam o cronograma da fábrica?"),
    ("analitica", "Existe algum componente crítico pendente que possa travar a nossa produção?"),

    ("analitica", "Quais são os fornecedores que mais atrasam as mercadorias?"),
    ("analitica", "Qual é o ranking de fornecedores com o pior prazo de entrega?"),
    ("analitica", "Quem são os parceiros comerciais com maior histórico de atrasos no recebimento?"),
    ("analitica", "Pode me mostrar quais empresas têm a taxa mais alta de entregas fora do prazo?"),

    ("analitica", "Quanto tempo, em média, levamos desde que a mercadoria chega até a nota dar entrada no sistema?"),
    ("analitica", "Qual é o tempo médio gasto na etapa de recebimento e conferência de materiais?"),
    ("analitica", "Qual a média de tempo que levamos para processar um recebimento completo?"),
    ("analitica", "Qual o tempo médio de atravessamento entre a chegada na doca e a efetivação no estoque?"),

    ("analitica", "Quais compras atrasadas têm risco de prejudicar o andamento das OPs?"),
    ("analitica", "Tem alguma ordem de produção ameaçada por falta de entrega de algum pedido?"),
    ("analitica", "Quais pedidos em aberto podem acabar gerando falta de material na fábrica?"),
    ("analitica", "Existem pedidos não recebidos que vão causar parada por falta de insumo nas ordens de produção?")
]


def _montar_perguntas(rng: random.Random) -> list[tuple[str, str, str | None]]:
    montadas = []
    for grupo, modelo in PERGUNTAS:
        pergunta, numero = modelo, None
        if PADRAO_NUMERO.search(modelo):
            numero = f"P{rng.randint(NUM_MIN, NUM_MAX):05d}"
            pergunta = PADRAO_NUMERO.sub(numero, modelo)
        montadas.append((grupo, pergunta, numero))
    return montadas

async def _executar(
    grupo: str, pergunta: str, numero: str | None, sem: asyncio.Semaphore, validar: bool
) -> dict:
    async with sem:
        inicio = time.perf_counter()
        result: dict = {}
        erro = None
        try:
            result = await sql_graph.ainvoke({"question": pergunta})
            erro = result.get("error")
        except Exception as e:
            erro = f"Falha no agente: {e}"
        tempo_ms = int((time.perf_counter() - inicio) * 1000)  # mede só o agente

        rows = result.get("rows", [])
        item = {
            "grupo": grupo,
            "numero_sorteado": numero,
            "pergunta": pergunta,
            "tabelas": result.get("tables", []),
            "sql": result.get("sql"),
            "resposta": result.get("answer", ""),
            "linhas": len(rows),
            "linhas_amostra": rows[:5],
            "tentativas": result.get("attempts", 0),
            "erro": erro,
            "tempo_ms": tempo_ms,
        }

        if validar:
            try:
                contexto = schema_context(item["tabelas"]) if item["tabelas"] else ""
            except Exception:
                contexto = ""
            item["validacao"] = await validar_execucao(
                pergunta, item["sql"], rows, item["resposta"], erro, contexto
            )
        return item

def _resumo(resultados: list[dict]) -> dict:
    validacoes = [(r["grupo"], r["validacao"]) for r in resultados if r.get("validacao")]

    def agregar(itens: list[dict]) -> dict:
        notas = [v["nota_media"] for v in itens if "nota_media" in v]
        return {
            "total": len(itens),
            "aprovadas": sum(v["veredito"] == "aprovada" for v in itens),
            "parciais": sum(v["veredito"] == "parcial" for v in itens),
            "reprovadas": sum(v["veredito"] == "reprovada" for v in itens),
            "indefinidas": sum(v["veredito"] == "indefinido" for v in itens),
            "nota_media": round(sum(notas) / len(notas), 2) if notas else None,
        }

    grupos = dict.fromkeys(g for g, _ in validacoes)
    return {
        "geral": agregar([v for _, v in validacoes]),
        "por_grupo": {g: agregar([v for gg, v in validacoes if gg == g]) for g in grupos},
    }

@router.post("/run")
async def run_batch(
    concurrency: int = Query(
        1, ge=1, le=5,
        description="Quantas perguntas rodar em paralelo. Use 1 para evitar limite de taxa do Gemini.",
    ),
    seed: int | None = Query(
        None,
        description="Repete o mesmo sorteio de números. Vazio = sorteio novo a cada execução.",
    ),
    validar: bool = Query(
        True, description="Avalia cada resposta com um LLM-juiz e inclui a nota no relatório."
    ),
):
    inicio = time.perf_counter()
    sem = asyncio.Semaphore(concurrency)

    seed_usada = seed if seed is not None else random.randrange(1_000_000)
    perguntas = _montar_perguntas(random.Random(seed_usada))

    resultados = await asyncio.gather(
        *(_executar(g, p, n, sem, validar) for g, p, n in perguntas)
    )

    total_ms = int((time.perf_counter() - inicio) * 1000)
    payload = {
        "executado_em": datetime.now().isoformat(timespec="seconds"),
        "seed": seed_usada,
        "total_perguntas": len(resultados),
        "com_erro": sum(1 for r in resultados if r["erro"]),
        "tempo_total_ms": total_ms,
        "concorrencia": concurrency,
        "validacao_ativa": validar,
        "resumo_validacao": _resumo(resultados),
        "resultados": resultados,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    arquivo = OUTPUT_DIR / f"lote_{datetime.now():%Y%m%d_%H%M%S}.json"
    arquivo.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    relatorio = arquivo.with_suffix(".html")
    relatorio.write_text(gerar_html(payload), encoding="utf-8")

    return {
        "arquivo": str(arquivo),
        "relatorio_html": str(relatorio),
        "relatorio_url": f"/batch/report/{arquivo.stem}",
        "seed": seed_usada,
        "total_perguntas": payload["total_perguntas"],
        "com_erro": payload["com_erro"],
        "tempo_total_ms": total_ms,
        "resumo_validacao": payload["resumo_validacao"],
    }


@router.get("/report/latest", response_class=HTMLResponse)
async def report_latest():
    arquivos = sorted(OUTPUT_DIR.glob("lote_*.html"))
    if not arquivos:
        raise HTTPException(status_code=404, detail="Nenhum relatório gerado ainda.")
    return HTMLResponse(arquivos[-1].read_text(encoding="utf-8"))


@router.get("/report/{nome}", response_class=HTMLResponse)
async def report(nome: str):
    arquivo = OUTPUT_DIR / f"{Path(nome).stem}.html"
    if not arquivo.exists():
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")
    return HTMLResponse(arquivo.read_text(encoding="utf-8"))