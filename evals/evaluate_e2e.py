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

    roteamento_ok = _ferramentas_usadas(trace) >= set(caso["ferramentas_esperadas"])
    citacao_ok = _citou_doc(trace, caso["doc_esperado"]) if caso.get("doc_esperado") else None
    veredito = julgar(cliente, caso["pergunta"], resposta, fatos)
    cobertura = min(1.0, len(veredito["cobertos"]) / len(fatos)) if fatos else 0.0

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
        "| Caso | Tipo | Rota | Cita | Cobertura | Aluc. | Nota | s |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in resultados:
        cita = "—" if r["citacao_ok"] is None else ("ok" if r["citacao_ok"] else "NAO")
        rota = "ok" if r["roteamento_ok"] else "NAO"
        aluc = "sim" if r["alucinacao"] else "nao"
        pior = f" (pior {r.get('pior', r['cobertura']):.0%})" if runs > 1 else ""
        linhas.append(
            f"| {r['id']} | {r['tipo']} | {rota} | {cita} "
            f"| {r['cobertura']:.0%}{pior} | {aluc} | {r['nota']:.1f} | {r['segundos']:.1f} |"
        )
    ausentes = [f"{r['id']}: {a}" for r in resultados for a in r["ausentes"]]
    if ausentes:
        linhas += ["", "## Fatos nao cobertos", ""]
        linhas += [f"- {a}" for a in ausentes]
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


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
            }
        )

    saida = Path(args.relatorio)
    gerar_relatorio(agregados, saida, runs=args.runs)
    print(f"\nRelatorio gravado em {saida}")


if __name__ == "__main__":
    main()
