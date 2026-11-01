"""Avaliacao end-to-end do SentinelaSOC: resposta final julgada por LLM.

Fluxo por caso do golden set (evals/golden_e2e.json):
1. Executa o agente completo (roteamento -> ferramentas -> resposta com streaming).
2. Verifica roteamento (ferramentas usadas vs esperadas) e citacao (doc esperado no rastro).
3. Casos SQL: derivam os fatos esperados executando a SQL de referencia AO VIVO.
4. Um juiz LLM (temperatura 0) pontua cobertura dos fatos e alucinacao.

Uso: python evals/evaluate_e2e.py [--casos id1 id2] [--relatorio evals/report_e2e.md]
Requer OPENAI_API_KEY/OPENAI_BASE_URL configurados (Ollama local por padrao).
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentinelasoc import db
from sentinelasoc.agent import AgenteSOC, extrair_json
from sentinelasoc.llm import OpenAILLMClient
from sentinelasoc.telemetry import get_logger

log = get_logger("evals.e2e")

JUDGE_PROMPT = """Voce e um avaliador rigoroso de respostas de um assistente de SOC. Julgue a RESPOSTA contra os FATOS ESPERADOS.

PERGUNTA DO ANALISTA:
{pergunta}

RESPOSTA DO ASSISTENTE:
{resposta}

FATOS ESPERADOS (a resposta correta deve conter estes fatos, em qualquer redacao):
{fatos}

Regras:
- Um fato esta "coberto" se a resposta o afirma corretamente (sinonimos e formatos
  diferentes de numero valem, ex.: 40,5% = 40.5%).
- "alucinacao" = true somente se a resposta afirma algo CONTRADITORIO a um fato
  esperado ou inventa numeros/documentos inexistentes.
Responda SOMENTE com JSON: {{"cobertos": ["fato coberto"], "ausentes": ["fato ausente"], "alucinacao": false, "nota": 5}}
nota: 1-5 (5 = cobre tudo, sem alucinacao)."""

# ── Metricas DeepEval-equivalente (nomes padrao do mercado) ──────────────────

FAITHFULNESS_PROMPT = """Voce mede FIDELIDADE (faithfulness): toda afirmacao da RESPOSTA deve ser
sustentada pelo CONTEXTO de evidencias que o agente recuperou (documentos + dados + ML).

CONTEXTO DE EVIDENCIAS (o que o agente realmente conseguiu):
{contexto}

RESPOSTA FINAL AO ANALISTA:
{resposta}

Tarefa:
1. Extraia as afirmacoes factuais da resposta (numeros, prazos, fontes, procedimentos).
2. Verifique quais sao sustentadas pelo contexto.

Regras:
- Afirmacao sustentada = contexto afirma explicitamente (sinonimos valem; 7 dias = 7 dias uteis NAO vale).
- Citacao de documento presente no contexto conta como sustentada.
Responda SOMENTE com JSON: {{"afirmacoes": 3, "suportadas": 3, "nao_suportadas": ["afirmacao sem sustento"]}}"""

RELEVANCY_PROMPT = """Voce mede RELEVANCIA DA RESPOSTA (answer relevancy): a resposta endereca o que a
pergunta pede, de forma completa e sem desviar do assunto?

PERGUNTA DO ANALISTA:
{pergunta}

RESPOSTA:
{resposta}

Escala:
- 1.0 = endereca exatamente o que foi perguntado, com completude.
- 0.5 = responde parcialmente ou desvia parte do foco.
- 0.0 = nao responde a pergunta.
Responda SOMENTE com JSON: {{"relevancia": 1.0, "motivo": "..."}}"""


def _carregar_casos() -> list[dict]:
    return json.loads((Path(__file__).parent / "golden_e2e.json").read_text(encoding="utf-8"))[
        "casos"
    ]


def _valores_da_referencia(sql: str) -> dict:
    """Executa a SQL de referencia e devolve dict de placeholders {n: valor, pct: valor}."""
    colunas, linhas = db.run_select(sql)
    if not linhas:
        return {}
    return {col: linhas[0][i] for i, col in enumerate(colunas)}


def derivar_fatos(caso: dict) -> list[str]:
    """Fatos finais do caso: fixos ou derivados da SQL de referencia (executada ao vivo)."""
    fatos = list(caso.get("fatos", []))
    if caso.get("sql_referencia"):
        valores = _valores_da_referencia(caso["sql_referencia"])
        for modelo in caso.get("fatos_template", []):
            try:
                fatos.append(modelo.format(**valores))
            except KeyError:
                fatos.append(modelo)
    return fatos


def julgar(cliente, pergunta: str, resposta: str, fatos: list[str]) -> dict:
    """Julga a resposta: cobertura de fatos + alucinacao (LLM, temperatura 0)."""
    prompt = JUDGE_PROMPT.format(
        pergunta=pergunta,
        resposta=resposta[:2500],
        fatos="\n".join(f"- {f}" for f in fatos),
    )
    try:
        veredito = extrair_json(
            cliente.complete(
                [{"role": "system", "content": prompt}, {"role": "user", "content": "julgue"}],
                temperature=0.0,
            )
        )
        return {
            "cobertos": list(veredito.get("cobertos", [])),
            "ausentes": list(veredito.get("ausentes", [])),
            "alucinacao": bool(veredito.get("alucinacao", False)),
            "nota": int(veredito.get("nota", 0)),
        }
    except (ValueError, KeyError) as exc:
        log.warning("judge.failed erro=%s", exc)
        return {"cobertos": [], "ausentes": fatos, "alucinacao": False, "nota": 0, "erro": str(exc)}


def medir_faithfulness(cliente, resposta: str, contexto: str) -> float | None:
    """Fidelidade (DeepEval-equivalente): fracao das afirmacoes da resposta
    sustentadas pelo contexto de evidencias. None quando nao ha contexto
    (respostas diretas, sem ferramentas)."""
    contexto = (contexto or "").strip()
    if not contexto:
        return None
    try:
        veredito = extrair_json(
            cliente.complete(
                [
                    {
                        "role": "system",
                        "content": FAITHFULNESS_PROMPT.format(
                            contexto=contexto[:3000], resposta=resposta[:2500]
                        ),
                    },
                    {"role": "user", "content": "medir"},
                ],
                temperature=0.0,
                json_mode=True,
            )
        )
        n = int(veredito.get("afirmacoes", 0))
        s = int(veredito.get("suportadas", 0))
        if n <= 0:  # resposta sem afirmacoes factuais: fiel por vacuidade
            return 1.0
        return min(1.0, s / n)
    except (ValueError, KeyError, TypeError) as exc:
        log.warning("faithfulness.failed erro=%s", exc)
        return None


def medir_relevancia(cliente, pergunta: str, resposta: str) -> float | None:
    """Answer relevancy (DeepEval-equivalente): 0-1 o quanto a resposta
    endereca a pergunta."""
    try:
        veredito = extrair_json(
            cliente.complete(
                [
                    {
                        "role": "system",
                        "content": RELEVANCY_PROMPT.format(
                            pergunta=pergunta, resposta=resposta[:2500]
                        ),
                    },
                    {"role": "user", "content": "medir"},
                ],
                temperature=0.0,
                json_mode=True,
            )
        )
        return max(0.0, min(1.0, float(veredito.get("relevancia", 0.0))))
    except (ValueError, KeyError, TypeError) as exc:
        log.warning("relevancy.failed erro=%s", exc)
        return None


def _normalizar_valor(v: object) -> str:
    """Valor de celula em forma comparavel (numero arredondado ou texto minusculo)."""
    try:
        return str(round(float(v), 2))
    except (TypeError, ValueError):
        return str(v).strip().lower()


def medir_sql_corretude(trace: list[dict], sql_referencia: str) -> float | None:
    """Correcao de SQL: executa a consulta GERADA pelo agente (do rastro) e a de
    REFERENCIA ao vivo no DuckDB e compara os resultados normalizados.
    1.0 = mesmo resultado; 0.0 = divergente; None = agente nao executou SQL."""
    sql_agente = next((t["sql"] for t in trace if t["tipo"] == "sql" and t.get("sql")), None)
    if not sql_agente:
        return None
    try:
        _, ref = db.run_select(sql_referencia)
        _, ger = db.run_select(sql_agente)
        norm_ref = sorted(tuple(_normalizar_valor(v) for v in linha) for linha in ref)
        norm_ger = sorted(tuple(_normalizar_valor(v) for v in linha) for linha in ger)
        return 1.0 if norm_ref == norm_ger else 0.0
    except Exception as exc:  # guarda rejeitou? banco falhou? -> divergente
        log.warning("sqlc.compare.failed erro=%s", exc)
        return 0.0


def _ferramentas_usadas(trace: list[dict]) -> set[str]:
    return {t["tipo"] for t in trace if t["tipo"] in ("sql", "rag")}


def _citou_doc(trace: list[dict], doc: str) -> bool:
    return any(
        t["tipo"] == "rag" and any(doc in fonte for fonte in t.get("fontes", [])) for t in trace
    )


def avaliar_caso(agente: AgenteSOC, cliente, caso: dict) -> dict:
    fatos = derivar_fatos(caso)
    inicio = time.perf_counter()
    resposta = "".join(agente.answer(caso["pergunta"]))
    duracao = round(time.perf_counter() - inicio, 1)
    trace = agente.last_trace
    contexto = agente.last_contexto

    roteamento_ok = _ferramentas_usadas(trace) >= set(caso["ferramentas_esperadas"])
    citacao_ok = _citou_doc(trace, caso["doc_esperado"]) if caso.get("doc_esperado") else None
    veredito = julgar(cliente, caso["pergunta"], resposta, fatos)
    cobertura = min(1.0, len(veredito["cobertos"]) / len(fatos)) if fatos else 0.0

    # metricas DeepEval-equivalente
    faithfulness = medir_faithfulness(cliente, resposta, contexto)
    relevancia = medir_relevancia(cliente, caso["pergunta"], resposta)
    sql_corretude = (
        medir_sql_corretude(trace, caso["sql_referencia"]) if caso.get("sql_referencia") else None
    )

    return {
        "id": caso["id"],
        "tipo": caso["tipo"],
        "resposta_trecho": resposta[:220].replace("\n", " "),
        "roteamento_ok": roteamento_ok,
        "citacao_ok": citacao_ok,
        "cobertura": round(cobertura, 2),
        "alucinacao": veredito["alucinacao"],
        "nota": veredito["nota"],
        "ausentes": veredito["ausentes"],
        "segundos": duracao,
        "faithfulness": round(faithfulness, 2) if faithfulness is not None else None,
        "relevancia": round(relevancia, 2) if relevancia is not None else None,
        "sql_corretude": sql_corretude,
    }


def gerar_relatorio(resultados: list[dict], caminho: Path, runs: int = 1) -> None:
    n = len(resultados)
    cob = sum(r["cobertura"] for r in resultados) / n
    rot = sum(r["roteamento_ok"] for r in resultados) / n
    alu = sum(r["alucinacao"] for r in resultados) / n
    nota = sum(r["nota"] for r in resultados) / n
    lat = sum(r["segundos"] for r in resultados) / n
    cits = [r for r in resultados if r["citacao_ok"] is not None]
    cit = (sum(1 for r in cits if r["citacao_ok"]) / len(cits)) if cits else None

    def _media(campo: str) -> float | None:
        vals = [r[campo] for r in resultados if r.get(campo) is not None]
        return (sum(vals) / len(vals)) if vals else None

    fidel = _media("faithfulness")
    relev = _media("relevancia")
    sqlc = _media("sql_corretude")

    linhas = [
        "# Avaliacao end-to-end — SentinelaSOC",
        "",
        f"Agente completo (roteamento -> ferramentas -> resposta) sobre o golden set de "
        f"{n} casos, {runs} corrida(s) por caso (media entre corridas; 'pior' = pior cobertura).",
        "Juiz: LLM local, temperatura 0. Casos SQL verificam numeros contra consulta de"
        " referencia executada ao vivo.",
        "",
        "| Metrica | Valor |",
        "|---|---|",
        f"| Cobertura de fatos (media) | {cob:.0%} |",
        f"| Roteamento correto | {rot:.0%} |",
        f"| Citacao do documento correto | {cit:.0%} |"
        if cit is not None
        else "| Citacao do documento correto | — |",
        f"| Respostas com alucinacao | {alu:.0%} |",
        f"| Nota media do juiz (1-5) | {nota:.1f} |",
        f"| Latencia media por resposta | {lat:.1f}s |",
        "",
        "## Metricas DeepEval-equivalente",
        "",
        "| Metrica | Definicao | Valor |",
        "|---|---|---|",
        "| **Faithfulness** | afirmacoes da resposta sustentadas pelas evidencias recuperadas | "
        + (f"{fidel:.0%}" if fidel is not None else "—")
        + " |",
        "| **Answer relevancy** | resposta endereca o que a pergunta pede (0-1) | "
        + (f"{relev:.0%}" if relev is not None else "—")
        + " |",
        "| **SQL correctness** | consulta gerada == consulta de referencia (executadas ao vivo) | "
        + (f"{sqlc:.0%}" if sqlc is not None else "—")
        + " |",
        "",
        "| Caso | Tipo | Rota | Cita | Fidel. | Relev. | SQL | Cobertura | Aluc. | Nota | s |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in resultados:
        cita = "—" if r["citacao_ok"] is None else ("ok" if r["citacao_ok"] else "NAO")
        rota = "ok" if r["roteamento_ok"] else "NAO"
        aluc = "sim" if r["alucinacao"] else "nao"
        pior = f" (pior {r.get('pior', r['cobertura']):.0%})" if runs > 1 else ""
        fid = "—" if r.get("faithfulness") is None else f"{r['faithfulness']:.0%}"
        rel = "—" if r.get("relevancia") is None else f"{r['relevancia']:.0%}"
        sqlc_c = "—" if r.get("sql_corretude") is None else f"{r['sql_corretude']:.0%}"
        linhas.append(
            f"| {r['id']} | {r['tipo']} | {rota} | {cita} | {fid} | {rel} | {sqlc_c} "
            f"| {r['cobertura']:.0%}{pior} | {aluc} | {r['nota']:.1f} | {r['segundos']:.1f} |"
        )
    ausentes = [f"{r['id']}: {a}" for r in resultados for a in r["ausentes"]]
    if ausentes:
        linhas += ["", "## Fatos nao cobertos", ""]
        linhas += [f"- {a}" for a in ausentes]

    # tendencia entre execucoes (historico acumulado)
    historico = _carregar_historico(caminho.parent / "historico_e2e.json")
    if historico:
        linhas += ["", "## Tendencia entre execucoes", ""]
        linhas += [
            "| Execucao | Runs | Cobertura | Fidel. | Relev. | SQL | Aluc. | Nota | Lat. |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for h in historico[-5:]:
            fid_h = "—" if h.get("faithfulness") is None else f"{h['faithfulness']:.0%}"
            rel_h = "—" if h.get("relevancia") is None else f"{h['relevancia']:.0%}"
            sql_h = "—" if h.get("sql_corretude") is None else f"{h['sql_corretude']:.0%}"
            linhas.append(
                f"| {h['data']} | {h['runs']} | {h['cobertura']:.0%} | {fid_h} | {rel_h} "
                f"| {sql_h} | {h['alucinacao']:.0%} | {h['nota']:.1f} | {h['latencia']:.1f}s |"
            )
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def _carregar_historico(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("historico.ilegivel erro=%s", exc)
        return []


def _registrar_historico(
    caminho: Path,
    resultados: list[dict],
    runs: int,
) -> None:
    """Acrescenta a corrida atual ao historico (para a secao de tendencia)."""
    n = len(resultados)

    def _media(campo: str) -> float | None:
        vals = [r[campo] for r in resultados if r.get(campo) is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    historico = _carregar_historico(caminho)
    historico.append(
        {
            "data": datetime.now().astimezone().isoformat(timespec="minutes"),
            "runs": runs,
            "casos": n,
            "cobertura": round(sum(r["cobertura"] for r in resultados) / n, 3),
            "roteamento": round(sum(r["roteamento_ok"] for r in resultados) / n, 3),
            "alucinacao": round(sum(r["alucinacao"] for r in resultados) / n, 3),
            "nota": round(sum(r["nota"] for r in resultados) / n, 2),
            "latencia": round(sum(r["segundos"] for r in resultados) / n, 1),
            "faithfulness": _media("faithfulness"),
            "relevancia": _media("relevancia"),
            "sql_corretude": _media("sql_corretude"),
        }
    )
    caminho.write_text(json.dumps(historico, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--casos", nargs="*", default=None, help="ids especificos (default: todos)")
    parser.add_argument(
        "--runs", type=int, default=1, help="corridas por caso (variancia do LLM local)"
    )
    parser.add_argument("--relatorio", default=str(Path(__file__).parent / "report_e2e.md"))
    args = parser.parse_args()

    casos = _carregar_casos()
    if args.casos:
        casos = [c for c in casos if c["id"] in args.casos]

    cliente = OpenAILLMClient()
    agente = AgenteSOC(llm=cliente)
    corridas: list[list[dict]] = []
    for run in range(1, args.runs + 1):
        resultados_run = []
        for i, caso in enumerate(casos, 1):
            log.info("e2e.case id=%s run=%d/%d (%d/%d)", caso["id"], run, args.runs, i, len(casos))
            resultado = avaliar_caso(agente, cliente, caso)
            resultados_run.append(resultado)
            print(
                f"[run {run}/{args.runs} {i}/{len(casos)}] {resultado['id']}: "
                f"cobertura={resultado['cobertura']:.0%} nota={resultado['nota']} "
                f"aluc={'sim' if resultado['alucinacao'] else 'nao'} ({resultado['segundos']}s)"
            )
        corridas.append(resultados_run)

    # agrega por caso entre corridas
    def _media_caso(da_caso: list[dict], campo: str) -> float | None:
        vals = [d[campo] for d in da_caso if d.get(campo) is not None]
        return sum(vals) / len(vals) if vals else None

    agregados = []
    for j in range(len(casos)):
        da_caso = [corridas[r][j] for r in range(args.runs)]
        coberturas = [d["cobertura"] for d in da_caso]
        agregados.append(
            {
                **da_caso[-1],
                "cobertura": sum(coberturas) / len(coberturas),
                "pior": min(coberturas),
                "nota": sum(d["nota"] for d in da_caso) / len(da_caso),
                "alucinacao": any(d["alucinacao"] for d in da_caso),
                "segundos": sum(d["segundos"] for d in da_caso) / len(da_caso),
                "faithfulness": _media_caso(da_caso, "faithfulness"),
                "relevancia": _media_caso(da_caso, "relevancia"),
                "sql_corretude": _media_caso(da_caso, "sql_corretude"),
            }
        )

    saida = Path(args.relatorio)
    _registrar_historico(saida.parent / "historico_e2e.json", agregados, runs=args.runs)
    gerar_relatorio(agregados, saida, runs=args.runs)
    print(f"\nRelatorio gravado em {saida}")


if __name__ == "__main__":
    main()
