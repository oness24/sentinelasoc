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
    llm = FakeLLM(complete_responses=[veredito], stream_chunks=["passos..."])
    agente = type("A", (), {"answer": lambda self, p: iter(["passos..."]), "last_trace": []})()
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
