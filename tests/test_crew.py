"""Testes da tripulacao (crew): dois agentes especializados no mesmo chat."""

import json

import pytest

from conftest import FakeLLM, rota_consultar
from sentinelasoc.agent import AgenteSOC


def _llm_sql() -> FakeLLM:
    return FakeLLM(
        complete_responses=[
            rota_consultar([{"tipo": "sql", "pergunta": "total de incidentes"}]),
            json.dumps({"sql": "SELECT COUNT(*) AS total FROM incidentes"}),
        ],
        stream_chunks=["Existem ", "356 incidentes."],
    )


def test_dois_agentes_no_mesmo_chat():
    """Triador coleta; redator redige — ambos registrados no rastro da MESMA resposta."""
    llm = _llm_sql()
    agente = AgenteSOC(llm=llm)
    saida = "".join(agente.answer("quantos incidentes existem?"))

    assert "356" in saida
    papeis = [t["papel"] for t in agente.last_trace if t["tipo"] == "agente"]
    assert "triador" in papeis, "triador deveria atuar"
    assert "redator" in papeis, "redator deveria atuar no mesmo chat"
    # ordem: triador (inicio) -> triador (entrega) -> redator
    assert papeis == ["triador", "triador", "redator"]


def test_entrega_triador_redator_registra_ferramentas():
    llm = _llm_sql()
    agente = AgenteSOC(llm=llm)
    "".join(agente.answer("quantos incidentes existem?"))

    entrega = next(
        t
        for t in agente.last_trace
        if t["tipo"] == "agente" and t["papel"] == "triador" and "dossi" in t["acao"]
    )
    assert "sql" in entrega["acao"]


def test_redator_recebe_dossie_e_guardrails():
    """O redator ve as evidencias do triador e o prompt com guardrails de redacao."""
    llm = _llm_sql()
    agente = AgenteSOC(llm=llm)
    "".join(agente.answer("quantos incidentes existem?"))

    # dossie exposto para avaliacao (Etapa D)
    assert "Resultado da consulta SQL" in agente.last_contexto
    assert "356" in agente.last_contexto
    # mensagem final: system com papel REDATOR + guardrails; user com contexto
    system = llm.stream_calls[0][0]["content"]
    assert "AGENTE REDATOR" in system
    assert "GUARDRAILS" in system
    user = llm.stream_calls[0][-1]["content"]
    assert "Resultado da consulta SQL" in user


def test_redator_recebe_perfil_do_analista():
    llm = FakeLLM(
        complete_responses=[rota_consultar([{"tipo": "rag", "consulta": "politica de senhas"}])],
        stream_chunks=["Resposta com perfil."],
    )
    agente = AgenteSOC(llm=llm)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("sentinelasoc.agent.rag.retrieve", lambda q, k=None: [])
        "".join(agente.answer("regras de senha?", perfil=["Analista prefere respostas curtas"]))
    assert "Analista prefere respostas curtas" in llm.stream_calls[0][0]["content"]


def test_social_e_respondida_pelo_triador_sem_redator():
    """Conversa social: 1 chamada, sem redator (decisao visivel no rastro)."""
    llm = FakeLLM(complete_responses=[json.dumps({"acao": "direto", "resposta": "Ola, analista!"})])
    agente = AgenteSOC(llm=llm)
    saida = "".join(agente.answer("oi"))
    assert saida == "Ola, analista!"
    assert len(llm.complete_calls) == 1
    assert len(llm.stream_calls) == 0
    assert not any(t.get("papel") == "redator" for t in agente.last_trace if t["tipo"] == "agente")
    assert agente.last_contexto == ""


def test_triador_usa_prompt_proprio():
    """A decisao de evidencias usa o prompt do TRIADOR (papel explicito na equipe)."""
    llm = _llm_sql()
    agente = AgenteSOC(llm=llm)
    "".join(agente.answer("quantos incidentes existem?"))
    # sem historico: complete_calls[0] = decisao do triador; [1] = geracao de SQL
    system_rota = llm.complete_calls[0][0]["content"]
    assert "AGENTE TRIADOR" in system_rota
    assert "sql" in system_rota  # herda as ferramentas do roteador
    system_sql = llm.complete_calls[1][0]["content"]
    assert "gerador de SQL" in system_sql


def test_formatar_evento_agente():
    from sentinelasoc.web.trace import formatar_evento

    chip, texto = formatar_evento(
        {"tipo": "agente", "papel": "redator", "acao": "redigindo resposta com guardrails"}
    )
    assert chip == "agente"
    assert texto.startswith("REDATOR")
    assert "redigindo" in texto
