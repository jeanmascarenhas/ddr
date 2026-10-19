from html import escape

CORES = {"aprovada": "#16a34a", "parcial": "#d97706", "reprovada": "#dc2626", "indefinido": "#6b7280"}
ROTULOS = {"aprovada": "Aprovada", "parcial": "Parcial", "reprovada": "Reprovada",
           "indefinido": "Indefinida", "sem_validacao": "Sem validação"}
CRITERIOS = {"fidelidade": "Fidelidade aos dados", "aderencia": "Aderência à pergunta",
             "sql": "Qualidade do SQL", "clareza": "Clareza"}

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--txt:#1f2937;--mudo:#6b7280;--borda:#e5e7eb}
@media (prefers-color-scheme:dark){:root{--bg:#111827;--card:#1f2937;--txt:#e5e7eb;--mudo:#9ca3af;--borda:#374151}}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--txt);line-height:1.45}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
h1{margin:0 0 4px;font-size:1.5rem}
h4{margin:16px 0 6px;font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;color:var(--mudo)}
.mudo{color:var(--mudo);font-size:.9rem}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:20px 0}
.kpi{background:var(--card);border:1px solid var(--borda);border-radius:10px;padding:14px}
.kpi b{display:block;font-size:1.6rem}
table{border-collapse:collapse;width:100%;font-size:.85rem}
th,td{border-bottom:1px solid var(--borda);padding:6px 8px;text-align:left;vertical-align:top}
.rolagem{overflow-x:auto}
.filtros{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0 12px}
.filtro{border:1px solid var(--borda);background:var(--card);color:var(--txt);border-radius:999px;padding:6px 14px;cursor:pointer}
.filtro.ativo{background:#2563eb;color:#fff;border-color:#2563eb}
.card{background:var(--card);border:1px solid var(--borda);border-left:6px solid var(--cor);border-radius:10px;margin-bottom:10px}
.card summary{cursor:pointer;padding:12px 14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.corpo{padding:0 14px 14px}
.badge{color:#fff;border-radius:6px;padding:2px 8px;font-size:.78rem;font-weight:600}
.tag{border:1px solid var(--borda);border-radius:6px;padding:1px 7px;font-size:.78rem;color:var(--mudo)}
.perg{flex:1 1 320px;font-weight:600}
pre{background:rgba(127,127,127,.12);padding:10px;border-radius:8px;white-space:pre-wrap;word-break:break-word;font-size:.82rem;margin:0}
.barra{display:flex;align-items:center;gap:10px;margin:4px 0;font-size:.88rem}
.rot{width:170px}
.trilho{flex:1;height:8px;background:rgba(127,127,127,.2);border-radius:99px;overflow:hidden}
.fill{height:100%}
ul.problemas{margin:4px 0;padding-left:20px}
.sugestao{border-left:3px solid #2563eb;padding:6px 10px;background:rgba(37,99,235,.08);border-radius:4px}
"""

JS = """
document.querySelectorAll('.filtro').forEach(function(b){
  b.addEventListener('click', function(){
    document.querySelectorAll('.filtro').forEach(function(x){x.classList.remove('ativo')});
    b.classList.add('ativo');
    var f = b.dataset.f;
    document.querySelectorAll('.card').forEach(function(c){
      c.style.display = (f === 'todas' || c.dataset.v === f) ? '' : 'none';
    });
  });
});
"""


def _fmt(valor, sufixo="") -> str:
    return "-" if valor is None else f"{valor}{sufixo}"


def _badge(veredito: str) -> str:
    cor = CORES.get(veredito, "#6b7280")
    return f'<span class="badge" style="background:{cor}">{ROTULOS.get(veredito, veredito)}</span>'


def _barra(rotulo: str, nota: int) -> str:
    cor = "#16a34a" if nota >= 4 else "#d97706" if nota == 3 else "#dc2626"
    return (f'<div class="barra"><span class="rot">{rotulo}</span>'
            f'<div class="trilho"><div class="fill" style="width:{nota * 20}%;background:{cor}"></div></div>'
            f'<b>{nota}/5</b></div>')


def _tabela(linhas: list[dict], total: int) -> str:
    if not linhas:
        return '<p class="mudo">Nenhuma linha retornada.</p>'
    cols = list(linhas[0].keys())
    cab = "".join(f"<th>{escape(str(c))}</th>" for c in cols)
    corpo = "".join(
        "<tr>" + "".join(f"<td>{escape(str(l.get(c, '')))}</td>" for c in cols) + "</tr>"
        for l in linhas
    )
    return (f'<p class="mudo">Mostrando {len(linhas)} de {total} linhas.</p>'
            f'<div class="rolagem"><table><thead><tr>{cab}</tr></thead><tbody>{corpo}</tbody></table></div>')


def _avaliacao(v: dict) -> str:
    if not v:
        return '<p class="mudo">Validação desativada nesta execução.</p>'
    if "notas" not in v:
        return f'<p class="mudo">{escape(v.get("erro", "Validação indisponível."))}</p>'
    partes = ["".join(_barra(rot, v["notas"][k]) for k, rot in CRITERIOS.items())]
    if v.get("resultado_vazio_plausivel") is not None:
        txt = "plausível (resultado legítimo)" if v["resultado_vazio_plausivel"] else "suspeito (possível falha na consulta)"
        partes.append(f'<p><b>Resultado vazio:</b> {txt}</p>')
    if v.get("problemas"):
        itens = "".join(f"<li>{escape(p)}</li>" for p in v["problemas"])
        partes.append(f'<h4>Problemas encontrados</h4><ul class="problemas">{itens}</ul>')
    if v.get("sugestao"):
        partes.append(f'<h4>Sugestão de ajuste</h4><div class="sugestao">{escape(v["sugestao"])}</div>')
    if v.get("justificativa"):
        partes.append(f'<h4>Justificativa do avaliador</h4><p>{escape(v["justificativa"])}</p>')
    return "".join(partes)


def _card(r: dict) -> str:
    v = r.get("validacao") or {}
    veredito = v.get("veredito", "sem_validacao")
    cor = CORES.get(veredito, "#6b7280")
    numero = f'<span class="tag">{escape(r["numero_sorteado"])}</span>' if r.get("numero_sorteado") else ""
    nota = f'<span class="tag">nota {v["nota_media"]}</span>' if "nota_media" in v else ""
    erro = f'<h4>Erro do pipeline</h4><pre>{escape(str(r["erro"]))}</pre>' if r.get("erro") else ""
    return f"""
<details class="card" data-v="{veredito}" style="--cor:{cor}">
  <summary>{_badge(veredito)}{nota}<span class="tag">{escape(r['grupo'])}</span>{numero}
    <span class="perg">{escape(r['pergunta'])}</span><span class="mudo">{r['tempo_ms']} ms</span></summary>
  <div class="corpo">
    <h4>Resposta do assistente</h4><pre>{escape(r.get('resposta') or '(vazia)')}</pre>
    <h4>SQL utilizado</h4><pre>{escape(r.get('sql') or '(nenhum SQL gerado)')}</pre>
    <h4>Dados retornados</h4>{_tabela(r.get('linhas_amostra', []), r.get('linhas', 0))}
    <h4>Avaliação</h4>{_avaliacao(v)}
    {erro}
    <p class="mudo">Tentativas: {r.get('tentativas', 0)} · Tabelas: {escape(', '.join(r.get('tabelas', [])) or '-')}
      · Tempo da validação: {_fmt(v.get('tempo_ms'), ' ms')}</p>
  </div>
</details>"""


def gerar_html(payload: dict) -> str:
    resumo = payload.get("resumo_validacao", {})
    geral = resumo.get("geral", {})
    resultados = payload["resultados"]

    kpis = [
        ("Perguntas", payload["total_perguntas"]),
        ("Aprovadas", _fmt(geral.get("aprovadas"))),
        ("Parciais", _fmt(geral.get("parciais"))),
        ("Reprovadas", _fmt(geral.get("reprovadas"))),
        ("Nota média (1-5)", _fmt(geral.get("nota_media"))),
        ("Com erro", payload["com_erro"]),
        ("Tempo total", f"{payload['tempo_total_ms'] / 1000:.1f}s"),
    ]
    kpi_html = "".join(f'<div class="kpi"><span class="mudo">{k}</span><b>{v}</b></div>' for k, v in kpis)

    linhas_grupo = "".join(
        f"<tr><td>{escape(g)}</td><td>{d['total']}</td><td>{d['aprovadas']}</td><td>{d['parciais']}</td>"
        f"<td>{d['reprovadas']}</td><td>{d['indefinidas']}</td><td>{_fmt(d['nota_media'])}</td></tr>"
        for g, d in resumo.get("por_grupo", {}).items()
    )
    tabela_grupo = (
        "<div class='rolagem'><table><thead><tr><th>Grupo</th><th>Total</th><th>Aprovadas</th><th>Parciais</th>"
        f"<th>Reprovadas</th><th>Indefinidas</th><th>Nota média</th></tr></thead><tbody>{linhas_grupo}</tbody></table></div>"
        if linhas_grupo else '<p class="mudo">Sem dados de validação.</p>'
    )

    contagem = {}
    for r in resultados:
        k = (r.get("validacao") or {}).get("veredito", "sem_validacao")
        contagem[k] = contagem.get(k, 0) + 1
    filtros = f'<button class="filtro ativo" data-f="todas">Todas ({len(resultados)})</button>' + "".join(
        f'<button class="filtro" data-f="{k}">{ROTULOS.get(k, k)} ({n})</button>' for k, n in contagem.items()
    )

    modelo = next((r["validacao"].get("modelo_juiz") for r in resultados if r.get("validacao")), "-")
    cards = "".join(_card(r) for r in resultados)

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório do lote {escape(payload['executado_em'])}</title><style>{CSS}</style></head><body><main>
<h1>Relatório de validação do lote</h1>
<p class="mudo">Executado em {escape(payload['executado_em'])} · seed {payload.get('seed', '-')} ·
concorrência {payload['concorrencia']} · modelo avaliador: {escape(str(modelo))}</p>
<p class="mudo">A validação é feita por LLM sem acesso ao banco: avalia a coerência entre pergunta, SQL, dados e resposta.
Não substitui a conferência com um gabarito.</p>
<div class="cards">{kpi_html}</div>
<h4>Resumo por grupo</h4>{tabela_grupo}
<div class="filtros">{filtros}</div>
{cards}
</main><script>{JS}</script></body></html>"""