"""Testes unitarios do harness de avaliacao e2e (sem rede)."""

import json
import sys
from pathlib import Path

from conftest import FakeLLM

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))

from evaluate_e2e import (
    _citou_doc,
    _ferramentas_usadas,
    avaliar_caso,
    derivar_fatos,
    julgar,
)


def test_derivar_fatos_executa_referencia():
    caso = {
        "id": "x",
        "tipo": "sql",
        "sql_referencia": "SELECT COUNT(*) AS n FROM incidentes",
        "fatos_template": ["{n} incidentes no total"],
    }
    fatos = derivar_fatos(caso)
    assert fatos == ["356 incidentes no total"]


def test_julgar_parseia_veredito():
    llm = FakeLLM(
        complete_responses=[
            json.dumps(
                {"cobertos": ["fato 1"], "ausentes": ["fato 2"], "alucinacao": False, "nota": 4},
                ensure_ascii=False,
            )
        ]
    )
    v = julgar(llm, "pergunta", "resposta", ["fato 1", "fato 2"])
    assert v["nota"] == 4
    assert v["ausentes"] == ["fato 2"]
    assert v["alucinacao"] is False


def test_julgar_falha_graciosamente():
    llm = FakeLLM(complete_responses=["sem json"])
    v = julgar(llm, "p", "r", ["fato"])
    assert v["nota"] == 0
    assert v["ausentes"] == ["fato"]


def test_ferramentas_usadas_do_trace():
    trace = [
        {"tipo": "request", "id": "ab"},
        {"tipo": "sql", "sql": "SELECT 1", "linhas": 1},
        {"tipo": "rag", "consulta": "x", "fontes": ["a.md"]},
    ]
    assert _ferramentas_usadas(trace) == {"sql", "rag"}


def test_citou_doc():
    trace = [{"tipo": "rag", "consulta": "x", "fontes": ["playbook_resposta_incidentes.md :: 5.1"]}]
    assert _citou_doc(trace, "playbook_resposta_incidentes.md")
    assert not _citou_doc(trace, "politica_de_seguranca.md")


def test_avaliar_caso_integra_metricas(monkeypatch):
    """Caso rag com fake: roteamento ok, citacao ok, juiz cobre 1 de 2 fatos."""
    veredito = json.dumps(
        {"cobertos": ["triagem"], "ausentes": ["monitorar 7 dias"], "alucinacao": False, "nota": 3},
        ensure_ascii=False,
    )
    relevancia = json.dumps({"relevancia": 1.0, "motivo": "responde direto"})
    llm = FakeLLM(complete_responses=[veredito, relevancia], stream_chunks=["passos..."])
    agente = type(
        "A",
        (),
        {
            "answer": lambda self, p: iter(["passos..."]),
            "last_trace": [],
            "last_contexto": "",
        },
    )()
    monkeypatch.setattr("evaluate_e2e._citou_doc", lambda trace, doc: True)
    caso = {
        "id": "phish",
        "pergunta": "passos para phishing?",
        "tipo": "rag",
        "ferramentas_esperadas": ["rag"],
        "doc_esperado": "playbook_resposta_incidentes.md",
        "fatos": ["triagem", "monitorar 7 dias"],
    }
    resultado = avaliar_caso(agente, llm, caso)
    assert resultado["cobertura"] == 0.5
    assert resultado["nota"] == 3
    assert resultado["citacao_ok"] is True
    assert resultado["ausentes"] == ["monitorar 7 dias"]
    # contexto vazio (stub): faithfulness nao se aplica; relevancia medida
    assert resultado["faithfulness"] is None
    assert resultado["relevancia"] == 1.0
    assert resultado["sql_corretude"] is None


def test_medir_faithfulness_parseia_e_calcula():
    from evaluate_e2e import medir_faithfulness

    llm = FakeLLM(complete_responses=[json.dumps({"afirmacoes": 4, "suportadas": 3})])
    assert medir_faithfulness(llm, "resposta", "contexto com evidencias") == 0.75


def test_medir_faithfulness_sem_contexto_e_vacuo():
    from evaluate_e2e import medir_faithfulness

    llm = FakeLLM(complete_responses=[])
    assert medir_faithfulness(llm, "r", "") is None  # sem contexto: nao se aplica
    assert medir_faithfulness(llm, "r", "   ") is None
    vazio = FakeLLM(complete_responses=[json.dumps({"afirmacoes": 0, "suportadas": 0})])
    assert medir_faithfulness(vazio, "oi!", "contexto") == 1.0  # sem afirmacoes: fiel


def test_medir_faithfulness_falha_graciosamente():
    from evaluate_e2e import medir_faithfulness

    llm = FakeLLM(complete_responses=["sem json"])
    assert medir_faithfulness(llm, "r", "contexto") is None


def test_medir_relevancia_limite_0a1():
    from evaluate_e2e import medir_relevancia

    llm = FakeLLM(complete_responses=[json.dumps({"relevancia": 1.5})])
    assert medir_relevancia(llm, "p", "r") == 1.0
    llm2 = FakeLLM(complete_responses=[json.dumps({"relevancia": -0.3})])
    assert medir_relevancia(llm2, "p", "r") == 0.0
    llm3 = FakeLLM(complete_responses=["sem json"])
    assert medir_relevancia(llm3, "p", "r") is None


def test_medir_sql_corretude_compara_com_referencia():
    from evaluate_e2e import medir_sql_corretude

    ref = "SELECT COUNT(*) AS n FROM incidentes"
    trace_ok = [{"tipo": "sql", "sql": "SELECT COUNT(*) AS total FROM incidentes", "linhas": 1}]
    assert medir_sql_corretude(trace_ok, ref) == 1.0  # mesmo numero, coluna diferente

    trace_div = [
        {
            "tipo": "sql",
            "sql": "SELECT COUNT(*) AS n FROM incidentes WHERE severidade='Critica'",
            "linhas": 1,
        }
    ]
    assert medir_sql_corretude(trace_div, ref) == 0.0

    assert medir_sql_corretude([], ref) is None  # agente nao executou SQL


def test_medir_sql_corretude_formato_diferente_de_numero():
    from evaluate_e2e import medir_sql_corretude

    ref = (
        "SELECT ROUND(100.0*SUM(CASE WHEN falso_positivo='Sim' THEN 1 ELSE 0 END)"
        "/COUNT(*),1) AS pct FROM incidentes WHERE tipo='Forca Bruta'"
    )
    trace = [
        {
            "tipo": "sql",
            "sql": (
                "SELECT ROUND(100.0 * SUM(CASE WHEN falso_positivo = 'Sim' THEN 1 ELSE 0 END)"
                " / COUNT(*), 1) AS pct FROM incidentes WHERE tipo = 'Forca Bruta'"
            ),
            "linhas": 1,
        }
    ]
    assert medir_sql_corretude(trace, ref) == 1.0  # espacos/maiusculas nao importam


def test_historico_acumula_e_relatorio_mostra_tendencia(tmp_path):
    from evaluate_e2e import _carregar_historico, _registrar_historico, gerar_relatorio

    resultado = {
        "id": "x",
        "tipo": "sql",
        "roteamento_ok": True,
        "citacao_ok": None,
        "cobertura": 1.0,
        "alucinacao": False,
        "nota": 5,
        "ausentes": [],
        "segundos": 4.2,
        "faithfulness": 1.0,
        "relevancia": 0.9,
        "sql_corretude": 1.0,
    }
    historico_path = tmp_path / "historico_e2e.json"
    _registrar_historico(historico_path, [resultado], runs=1)
    _registrar_historico(historico_path, [resultado], runs=3)
    historico = _carregar_historico(historico_path)
    assert len(historico) == 2 and historico[-1]["runs"] == 3

    gerar_relatorio([resultado], tmp_path / "report_e2e.md", runs=1)
    texto = (tmp_path / "report_e2e.md").read_text(encoding="utf-8")
    assert "Metricas DeepEval-equivalente" in texto
    assert "Faithfulness" in texto and "Answer relevancy" in texto and "SQL correctness" in texto
    assert "Tendencia entre execucoes" in texto
